#!/usr/bin/python
# Copyright: (c) 2018, Manuel Maestinger <manuel.maestinger@inf.ethz.ch>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

#
# Simple inventory script to allow implicit definition of hosts via
# files in host_vars. The file must match host_vars/FQDN.yml! An
# explicit definition in a yaml or ini file would be required
# in addition to host_vars otherwise.
#
# Due to https://github.com/ansible/ansible/issues/44382, we need
# to parse the host_vars file to allow the constructed plugin to
# access these variables.
#

import os, glob, argparse, json, yaml

cwd = os.path.dirname(os.path.realpath(__file__))
varsglob = glob.glob(os.path.join(cwd, 'host_vars', '*.yml'))
hosts = [os.path.basename(os.path.splitext(x)[0]) for x in varsglob]

#
# Functions
#

def list_vars(hostvars):
    return {
        '_meta': {
            'hostvars': {host:var if var is not None else {} for (host,var) in hostvars.items()}
        }
    }

def list_all():
    hostvars = {host:list_host(host)['_meta']['hostvars'][host] for host in hosts}
    ret = list_vars(hostvars)
    ret.update({
        'all': {
            'hosts': hosts,
            'vars': {}
        }
    })
    return ret

def list_host(host):
    if host not in hosts:
        return list_vars({})

    vars_file = os.path.join(cwd, 'host_vars', '%s.yml' % host)
    try:
        return list_vars({host:yaml.load(open(vars_file))})
    except yaml.YAMLError as e:
        print('Syntax error in %s' % vars_file)
        exit(1)
    except:
        print('Could not read %s' % vars_file)
        exit(1)

#
# Arguments
#

parser = argparse.ArgumentParser()
parser.add_argument('--list', action = 'store_true')
parser.add_argument('--host', action = 'store')
args = parser.parse_args()

if args.list:
    print(json.dumps(list_all()))
elif args.host:
    print(json.dumps(list_host(args.host)))
else:
    print(json.dumps(list_vars({})))
