#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import time
import uuid

from collections import Counter

import networkx as nx

from solar.dblayer.model import clear_cache
from solar.dblayer.model import ModelMeta
from solar.dblayer.solar_models import Task
from solar import errors
from solar.orchestration.traversal import states
from solar import utils


def save_graph(graph):
    # maybe it is possible to store part of information in AsyncResult backend
    uid = graph.graph['uid']

    # TODO(dshulyak) remove duplication of parameters
    # in solar_models.Task and this object
    for n in nx.topological_sort(graph):
        t = Task.new(
            {'name': n,
             'execution': uid,
             'status': graph.node[n].get('status', ''),
             'target': graph.node[n].get('target', '') or '',
             'task_type': graph.node[n].get('type', ''),
             'args': graph.node[n].get('args', []),
             'errmsg': graph.node[n].get('errmsg', '') or '',
             'timelimit': graph.node[n].get('timelimit', 0),
             'retry': graph.node[n].get('retry', 0),
             'timeout': graph.node[n].get('timeout', 0),
             'start_time': 0.0,
             'end_time': 0.0})
        graph.node[n]['task'] = t
        for pred in graph.predecessors(n):
            pred_task = graph.node[pred]['task']
            t.parents.add(pred_task)
            pred_task.save()
        t.save()


def update_graph(graph, force=False):
    for n in graph:
        task = graph.node[n]['task']
        task.status = graph.node[n]['status']
        task.errmsg = graph.node[n]['errmsg'] or ''
        task.retry = graph.node[n].get('retry', 0)
        task.timeout = graph.node[n].get('timeout', 0)
        task.start_time = graph.node[n].get('start_time', 0.0)
        task.end_time = graph.node[n].get('end_time', 0.0)
        task.save(force=force)


def set_states(uid, tasks):
    plan = get_graph(uid)
    for t in tasks:
        if t not in plan.node:
            raise Exception("No task %s in plan %s", t, uid)
        plan.node[t]['task'].status = states.NOOP.name
        plan.node[t]['task'].save_lazy()
    ModelMeta.save_all_lazy()


def get_graph(uid):
    dg = nx.MultiDiGraph()
    dg.graph['uid'] = uid
    dg.graph['name'] = uid.split(':')[0]
    tasks = map(Task.get, Task.execution.filter(uid))
    for t in tasks:
        dg.add_node(
            t.name, status=t.status,
            type=t.task_type, args=t.args,
            target=t.target or None,
            errmsg=t.errmsg or None,
            task=t,
            timelimit=t.timelimit,
            retry=t.retry,
            timeout=t.timeout,
            start_time=t.start_time,
            end_time=t.end_time)
        for u in t.parents.all_names():
            dg.add_edge(u, t.name)
    return dg


def longest_path_time(graph):
    """We are not interested in the path itself, just get the start
    of execution and the end of it.
    """
    start = None
    end = None
    for n in graph:
        node_start = graph.node[n]['start_time']
        node_end = graph.node[n]['end_time']
        if node_start is 0.0 or node_end is 0.0:
            continue

        if node_start < start or start is None:
            start = node_start

        if node_end > end or end is None:
            end = node_end
    return end - start


def total_delta(graph):
    delta = 0.0
    for n in graph:
        node_start = graph.node[n]['start_time']
        node_end = graph.node[n]['end_time']
        if node_start is 0.0 or node_end is 0.0:
            continue
        delta += node_end - node_start
    return delta


get_plan = get_graph


def parse_plan(plan_path):
    """parses yaml definition and returns graph"""
    plan = utils.yaml_load(plan_path)
    dg = nx.MultiDiGraph()
    dg.graph['name'] = plan['name']
    for task in plan['tasks']:
        defaults = {
            'status': 'PENDING',
            'errmsg': '',
        }
        defaults.update(task['parameters'])
        dg.add_node(
            task['uid'], **defaults)
        for v in task.get('before', ()):
            dg.add_edge(task['uid'], v)
        for u in task.get('after', ()):
            dg.add_edge(u, task['uid'])
    return dg


def create_plan_from_graph(dg, save=True):
    dg.graph['uid'] = "{0}:{1}".format(dg.graph['name'], str(uuid.uuid4()))
    if save:
        save_graph(dg)
    return dg


def show(uid):
    dg = get_graph(uid)
    result = {}
    tasks = []
    result['uid'] = dg.graph['uid']
    result['name'] = dg.graph['name']
    for n in nx.topological_sort(dg):
        data = dg.node[n]
        tasks.append(
            {'uid': n,
             'parameters': data,
             'before': dg.successors(n),
             'after': dg.predecessors(n)
             })
    result['tasks'] = tasks
    return utils.yaml_dump(result)


def create_plan(plan_path, save=True):
    dg = parse_plan(plan_path)
    return create_plan_from_graph(dg, save=save)


def reset_by_uid(uid, state_list=None):
    dg = get_graph(uid)
    return reset(dg, state_list=state_list)


def reset(graph, state_list=None):
    for n in graph:
        if state_list is None or graph.node[n]['status'] in state_list:
            graph.node[n]['status'] = states.PENDING.name
    update_graph(graph)


def reset_filtered(uid):
    reset_by_uid(uid, state_list=[states.SKIPPED.name, states.NOOP.name])


def report_progress(uid):
    return report_progress_graph(get_graph(uid))


def report_progress_graph(dg):
    tasks = []
    report = {
        'total_time': longest_path_time(dg),
        'total_delta': total_delta(dg),
        'tasks': tasks}

    for task in nx.topological_sort(dg):
        data = dg.node[task]
        tasks.append([
            task,
            data['status'],
            data['errmsg'],
            data.get('start_time'),
            data.get('end_time')])

    return report


def wait_finish(uid, timeout):
    """Check if graph is finished

    Will return when no PENDING or INPROGRESS otherwise yields summary
    """
    start_time = time.time()

    while start_time + timeout >= time.time():
        # need to clear cache before fetching updated status
        clear_cache()
        dg = get_graph(uid)
        summary = Counter()
        summary.update({s.name: 0 for s in states})
        summary.update([s['status'] for s in dg.node.values()])
        yield summary
        if summary[states.PENDING.name] + summary[states.INPROGRESS.name] == 0:
            return

    else:
        raise errors.ExecutionTimeout(
            'Run %s wasnt able to finish' % uid)
