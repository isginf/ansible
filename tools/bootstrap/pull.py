#!/usr/bin/python
# Copyright: (c) 2018, Manuel Maestinger <manuel.maestinger@inf.ethz.ch>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import cgitb, os, socket, subprocess, yaml, binascii

###### UNCOMMENT TO DEBUG #######
# cgitb.enable(format = 'plain')
#################################

print('Content-Type: text/plain\n')

#
# Functions
#

def abort(msg):
    print('\n'.join([''.join(['# ', l]) for l in msg.split('\n')]))
    exit(0)

#
# Collect data
#

cwd = os.path.dirname(os.path.realpath(__file__))

#
# Read config
#

try:
    conf = yaml.load(open(os.path.join(cwd, 'pull.yml')))
except yaml.YAMLError as e:
    abort('Error in config file %s' % str(e))
except:
    abort('Error: Could not read config file %s' % os.path.join(cwd, 'pull.yml'))

# Allow relative paths
for repo in conf['repos'].keys():
    if not os.path.isabs(conf['repos'][repo]):
        conf['repos'][repo] = os.path.join(cwd, conf['repos'][repo])

#
# Checks
#

try:
    url = os.getenv('PATH_INFO').split('/')
    script, repo = url
    if repo not in conf['repos'].keys():
        raise Exception()
except:
    abort('Error: Invalid URL, try https://SERVER/git-pull/(%s)' % '|'.join(conf['repos'].keys()))

try:
    hostip = os.getenv('REMOTE_ADDR')
    if hostip not in conf['remote_ip']:
        raise Exception()
except:
    abort('Error: Not in the list of allowed hosts: %s' % ', '.join(conf['remote_ip']))

#
# Pull
#

for command in conf['commands']:
    try:
        git = subprocess.Popen(
            command.split(' '),
            cwd = conf['repos'][repo],
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
        )
        stdout, stderr = git.communicate()
        if git.returncode != 0:
            abort('Error in %s: %s' % (command, str(stderr)))
    except IOError:
        abort('Error: Could not run git')

abort('Success')
