#!/usr/bin/python
# Copyright: (c) 2018, Manuel Maestinger <manuel.maestinger@inf.ethz.ch>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import cgitb, os, socket, datetime, subprocess, jinja2, yaml, re, binascii

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

try:
    url = os.getenv('PATH_INFO').split('/')
    script, os_name, os_version, filename = url
except:
    abort('Error: Invalid URL, try https://SERVER/bootstrap/os_name/os_version/filename')

try:
    hostip = os.getenv('REMOTE_ADDR')
    hostname = socket.gethostbyaddr(hostip)[0]
except:
    abort('Error: Could not determine hostname of remote address')

#
# Read config
#

try:
    conf = yaml.load(open(cwd + '/cgi.yml'))
except yaml.YAMLError as e:
    abort('Error in config file %s' % str(e))
except:
    abort('Error: Could not read config file %s' % os.path.join(cwd, 'cgi.yml'))

# Allow relative paths
for dir in ['bootlink_dir', 'inventory_dir', 'template_dir', 'vars_dir']:
    if not os.path.isabs(conf[dir]):
        conf[dir] = os.path.join(cwd, conf[dir])

#
# Checks
#

if os_name not in conf['filenames'].keys():
    abort('Error: Undefined OS, try one of: %s' % ', '.join(conf['filenames'].keys()))

if not re.match(conf['patterns']['version'], os_version):
    abort('Error: OS version does not match %s' % conf['patterns']['version'])

if filename not in conf['filenames'][os_name]:
    abort('Error: Filename not defined for OS %s, try one of: %s' % (os_name, ', '.join(conf['filenames'][os_name])))

if not re.match(conf['patterns']['hostname'], hostname):
    abort('Error: Hostname does not match %s' % conf['patterns']['hostname'])

if conf['bootlink_check']:
    hostip_hex = binascii.hexlify(socket.inet_aton(hostip)).upper()
    if not os.path.exists(os.path.join(conf['bootlink_dir'], hostip_hex)):
        abort('Error: No bootlink found for %s' % hostip)

#
# Read inventory
#

try:
    ansible = subprocess.Popen(
        ['ansible-inventory', '-y', '-i', conf['inventory_dir'], '--host', hostname],
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE,
    )
    stdout, stderr = ansible.communicate()
    if ansible.returncode == 5:
        abort('Error: Host %s is not in inventory' % hostname)
    elif ansible.returncode != 0:
        abort('Error in Ansible: %s' % str(stderr))
    inventory = yaml.load(stdout)
except yaml.YAMLError as e:
    abort('Error: Ansible returned invalid yaml data: %s' % str(e))
except IOError:
    abort('Error: Could not run Ansible')

#
# Collect and expand variables
#

# Add inventory
data = inventory.copy()

# Add server data
data.update({
    'os_name': os_name,
    'os_version': os_version,
    'filename': filename,
    'hostname': hostname,
})

# Expand vars_files
vars_files = []
for file in conf['vars_files']:
    vars_files.append(
        jinja2.Environment(loader=jinja2.BaseLoader).from_string(file).render(data)
    )

# Add vars_files data
for file in vars_files:
    if os.path.exists(os.path.join(conf['vars_dir'], file)):
        try:
            data.update(yaml.load(open(os.path.join(conf['vars_dir'], file))))
        except yaml.YAMLError as e:
            abort('Error in vars file %s' % str(e))
        except:
            abort('Error: Could not read vars file %s' % os.path.join(conf['vars_dir'], file))

# Expand template_files
template_files = []
for file in conf['template_files']:
    template_files.append(
        jinja2.Environment(loader=jinja2.BaseLoader).from_string(file).render(data)
    )

# Find template
template = ''
for file in template_files:
    if os.path.exists(os.path.join(conf['template_dir'], file)):
        template = file
        break
if template == '':
    abort('Error: No template found')

# Add template data
data.update({
    'template': template,
    'vars_files': vars_files,
    'template_files': template_files,
    'date': datetime.datetime.today().strftime('%Y-%m-%d'),
    'time': datetime.datetime.today().strftime('%H:%M:%S'),
})

#
# Load template
#

try:
    tpl = jinja2.Environment(
        loader=jinja2.FileSystemLoader(conf['template_dir'])
    ).get_template(template)
    print(tpl.render(data))
except jinja2.TemplateError as e:
    abort('Error %s in %s: %s' % (str(e.__class__.__name__), template, str(e.message)))
except:
    abort('Error: Could not read template')
