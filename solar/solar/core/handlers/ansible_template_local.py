# -*- coding: utf-8 -*-
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

from fabric.state import env
import os
from fabric import api as fabric_api

from solar.core.log import log
from solar.core.handlers.ansible_template import AnsibleTemplate
from solar import errors

# otherwise fabric will sys.exit(1) in case of errors
env.warn_only = True

class AnsibleTemplateLocal(AnsibleTemplate):

    def action(self, resource, action_name):
        inventory_file = self._create_inventory(resource)
        playbook_file = self._create_playbook(resource, action_name)
        log.debug('inventory_file: %s', inventory_file)
        log.debug('playbook_file: %s', playbook_file)

        call_args = ['ansible-playbook', '--module-path', '/tmp/library', '-i', inventory_file, playbook_file]
        log.debug('EXECUTING: %s', ' '.join(call_args))

        # out = self.transport_run.run(resource, *call_args)

        with fabric_api.shell_env(ANSIBLE_HOST_KEY_CHECKING='False'):
            out = fabric_api.local(' '.join(call_args), capture=True)
        if out.failed:
            raise errors.SolarError(out)

    def _render_inventory(self, r):
        inventory = '{0} ansible_ssh_host={1} ansible_connection=ssh ansible_ssh_user={2} ansible_ssh_private_key_file={3} {4}'
        host = r.ip()
        ssh_transport = next(x for x in  r.transports() if x.name == 'ssh')
        user = ssh_transport['user']
        ssh_key = ssh_transport['ssh_key']
        args = []
        for arg in r.args:
            args.append('{0}="{1}"'.format(arg, r.args[arg].value))
        args = ' '.join(args)
        inventory = inventory.format(host, host, user, ssh_key, args)
        log.debug(inventory)
        return inventory

    def _make_args(self, resource):
        args = super(AnsibleTemplateLocal, self)._make_args(resource)
        args['host'] = resource.ip()
        return args
