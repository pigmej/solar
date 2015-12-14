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

import os
import pytest
from solar.core.resource.repository import Repository


Repository._REPOS_LOCATION = '/tmp'


_META_CONTENT = """
handler: null
version: {0}
input:
  a:
    value: 1
    schema: int!
  name:
    value: {1}
  version:
    value: {0}
"""

_VERSIONS = ('0.0.1', '0.0.2', '1.0.0', '1.4.7', '2.0.0')


def generate_structure(target, versions='1.0.0'):
    if isinstance(versions, basestring):
        versions = (versions)
    elif isinstance(versions, int):
        versions = _VERSIONS[:versions]

    for name in ('first', 'second', 'third'):
        for version in versions:
            cnt = _META_CONTENT.format(version, name)
            fp = os.path.join(target, name, version)
            os.makedirs(fp)
            with open(os.path.join(fp, 'meta.yaml'), 'wb') as f:
                f.write(cnt)


@pytest.fixture(scope='module', autouse=True)
def repos_path(tmpdir_factory):
    Repository._REPOS_LOCATION = str(tmpdir_factory.mktemp('repositories'))
    return Repository._REPOS_LOCATION


@pytest.fixture(scope="function")
def ct(tmpdir_factory):
    rp = str(tmpdir_factory.mktemp('resources'))
    generate_structure(rp, 3)
    return rp


@pytest.fixture(scope="module")
def repo_r(tmpdir_factory):
    path = ct(tmpdir_factory)
    r = Repository('rtest')
    r.create(path)
    return r


@pytest.fixture(scope='function')
def repo_w(tmpdir_factory):
    path = ct(tmpdir_factory)
    r = Repository('rwtest')
    r.create(path)
    return r


def test_simple_create(ct):
    r = Repository('test')
    r.create(ct)
    for k, v in r.get_contents().items():
        assert len(v) == 3


@pytest.mark.parametrize('spec, exp',
                         (('rtest/first:0.0.1', True),
                          ('rtest/first:0.0.5', False),
                          ('invalid/first:0.0.5', False),
                          ('invalid/first:0.0.1', False)))
def test_simple_select(repo_r, spec, exp):
    spec = Repository._parse_spec(spec)
    assert Repository.contains(spec) == bool(exp)
    if exp:
        metadata = Repository.get_metadata(spec)
        assert metadata['version'] == spec['version']
        assert spec['version_sign'] == '=='


@pytest.mark.parametrize('spec, exp, exp_ver',
                         (('rtest/first:0.0.1', True, '0.0.1'),
                          ('rtest/first:==0.0.1', True, '0.0.1'),
                          ('rtest/first:==0.0.1', True, '0.0.1'),
                          ('rtest/first:<=0.0.5', True, '0.0.2'),
                          ('rtest/first:>=0.0.5', True, '1.0.0'),
                          ('rtest/first:>=1.0.0', True, '1.0.0')))
def test_guess_version_sharp(repo_r, spec, exp, exp_ver):
    assert Repository.contains(spec) == bool(exp)
    if exp:
        metadata = Repository.get_metadata(spec)
        assert metadata['version'] == exp_ver


@pytest.mark.parametrize('spec, exp, exp_ver',
                         (('rtest/first:<0.0.1', False, ''),
                          ('rtest/first:<0.0.2', True, '0.0.1'),
                          ('rtest/first:<0.0.5', True, '0.0.2'),
                          ('rtest/first:>0.0.5', True, '1.0.0'),
                          ('rtest/first:>1.0.0', False, '')))
def test_guess_version_soft(repo_r, spec, exp, exp_ver):
    assert Repository.contains(spec) == bool(exp)
    if exp:
        metadata = Repository.get_metadata(spec)
        assert metadata['version'] == exp_ver
