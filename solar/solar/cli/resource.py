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

import sys
import os
import json
import yaml
import tabulate

import click

from solar.core import actions
from solar.core import resource as sresource
from solar.core.resource import virtual_resource as vr
from solar.core.log import log
from solar import errors
from solar.interfaces import orm
from solar import utils

from solar.cli import executors


@click.group()
def resource():
    pass

@resource.command()
@click.argument('action')
@click.argument('resource')
@click.option('-d', '--dry-run', default=False, is_flag=True)
@click.option('-m', '--dry-run-mapping', default='{}')
def action(dry_run_mapping, dry_run, action, resource):
    if dry_run:
        dry_run_executor = executors.DryRunExecutor(mapping=json.loads(dry_run_mapping))

    click.echo(
        'action {} for resource {}'.format(action, resource)
    )

    r = sresource.load(resource)
    try:
        actions.resource_action(r, action)
    except errors.SolarError as e:
        log.debug(e)
        sys.exit(1)

    if dry_run:
        click.echo('EXECUTED:')
        for key in dry_run_executor.executed:
            click.echo('{}: {}'.format(
                click.style(dry_run_executor.compute_hash(key), fg='green'),
                str(key)
            ))

@resource.command()
@click.argument('resource')
def backtrack_inputs(resource):
    r = sresource.load(resource)

    inputs = []

    def backtrack(i):
        def format_input(i):
            return '{}::{}'.format(i.resource.name, i.name)

        if isinstance(i, list):
            return [backtrack(bi) for bi in i]

        if isinstance(i, dict):
            return {
                k: backtrack(bi) for k, bi in i.items()
            }

        bi = i.backtrack_value_emitter(level=1)
        if isinstance(i, orm.DBResourceInput) and isinstance(bi, orm.DBResourceInput) and i == bi:
            return (format_input(i), )

        return (format_input(i), backtrack(bi))

    for i in r.resource_inputs().values():
        click.echo(yaml.safe_dump({i.name: backtrack(i)}, default_flow_style=False))

@resource.command()
def compile_all():
    from solar.core.resource import compiler

    destination_path = utils.read_config()['resources-compiled-file']

    if os.path.exists(destination_path):
        os.remove(destination_path)

    for path in utils.find_by_mask(utils.read_config()['resources-files-mask']):
        meta = utils.yaml_load(path)
        meta['base_path'] = os.path.dirname(path)

        compiler.compile(meta)

@resource.command()
def clear_all():
    click.echo('Clearing all resources and connections')
    orm.db.clear()

@resource.command()
@click.argument('name')
@click.argument(
    'base_path', type=click.Path(exists=True, resolve_path=True))
@click.argument('args', nargs=-1)
def create(args, base_path, name):
    args_parsed = {}

    click.echo('create {} {} {}'.format(name, base_path, args))
    for arg in args:
        try:
            args_parsed.update(json.loads(arg))
        except ValueError:
            k, v = arg.split('=')
            args_parsed.update({k: v})
    resources = vr.create(name, base_path, args=args_parsed)
    for res in resources:
        click.echo(res.color_repr())

@resource.command()
@click.option('--name', default=None)
@click.option('--tag', default=None)
@click.option('--json', default=False, is_flag=True)
@click.option('--color', default=True, is_flag=True)
def show(**kwargs):
    resources = []

    for res in sresource.load_all():
        show = True
        if kwargs['tag']:
            if kwargs['tag'] not in res.tags:
                show = False
        if kwargs['name']:
            if res.name != kwargs['name']:
                show = False

        if show:
            resources.append(res)

    echo = click.echo_via_pager
    if kwargs['json']:
        output = json.dumps([r.to_dict() for r in resources], indent=2)
        echo = click.echo
    else:
        if kwargs['color']:
            formatter = lambda r: r.color_repr()
        else:
            formatter = lambda r: unicode(r)
        output = '\n'.join(formatter(r) for r in resources)

    if output:
        echo(output)

@resource.command()
@click.argument('resource_name')
@click.argument('tag_name')
@click.option('--add/--delete', default=True)
def tag(add, tag_name, resource_name):
    click.echo('Tag {} with {} {}'.format(resource_name, tag_name, add))
    r = sresource.load(resource_name)
    if add:
        r.add_tag(tag_name)
    else:
        r.remove_tag(tag_name)
    # TODO: the above functions should save resource automatically to the DB

@resource.command()
@click.argument('name')
@click.argument('args', nargs=-1)
def update(name, args):
    args_parsed = {}
    for arg in args:
        try:
            args_parsed.update(json.loads(arg))
        except ValueError:
            k, v = arg.split('=')
            args_parsed.update({k: v})
    click.echo('Updating resource {} with args {}'.format(name, args_parsed))
    res = sresource.load(name)
    res.update(args_parsed)

@resource.command()
@click.option('--check-missing-connections', default=False, is_flag=True)
def validate(check_missing_connections):
    errors = sresource.validate_resources()
    for r, error in errors:
        click.echo('ERROR: %s: %s' % (r.name, error))

    if check_missing_connections:
        missing_connections = vr.find_missing_connections()
        if missing_connections:
            click.echo(
                'The following resources have inputs of the same value '
                'but are not connected:'
            )
            click.echo(
                tabulate.tabulate([
                    ['%s::%s' % (r1, i1), '%s::%s' % (r2, i2)]
                    for r1, i1, r2, i2 in missing_connections
                ])
            )

@resource.command()
@click.argument('path', type=click.Path(exists=True, dir_okay=False))
def get_inputs(path):
    with open(path) as f:
        content = f.read()
    click.echo(vr.get_inputs(content))

@resource.command()
@click.argument('name')
@click.option('-f', default=False, help='force removal from database')
def remove(name, f):
    res = sresource.load(name)
    res.remove(force=f)