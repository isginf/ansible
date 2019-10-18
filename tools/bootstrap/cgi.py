#!/usr/bin/python
# Copyright: (c) 2018, Manuel Maestinger <manuel.maestinger@inf.ethz.ch>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import os, sys, socket, datetime, subprocess, jinja2, yaml, re, binascii, traceback

############# UNCOMMENT TO DEBUG ##############
# import cgitb; cgitb.enable(format = 'plain')
###############################################

#
# Functions
#

def ansible_inventory(inventory_dir, host, ignore_ansible_stderr=True):
    from ansible.vars.manager import VariableManager
    from ansible.inventory.manager import InventoryManager
    from ansible.parsing.dataloader import DataLoader

    # bug solved in ansible 2.6+: printing an empty stderr!
    if ignore_ansible_stderr: sys.stderr = open(os.devnull, 'w')

    loader = DataLoader()
    inventory = InventoryManager(loader=loader, sources=unicode(inventory_dir))
    vm = VariableManager(loader=loader, inventory=inventory)

    hosts = inventory.get_hosts(unicode(host))

    if len(hosts) != 1:
        raise KeyError('Host %s does not match a (single) host in %s' % (host, inventory_dir))

    hostvars = vm.get_vars(host=hosts[0], include_hostvars=False)

    # restore default
    if ignore_ansible_stderr: sys.stderr = sys.__stderr__

    return hostvars

def j2_render_dict(d, data):
    r = {};
    for k, v in d.items():
        if isinstance(v, dict):
            r.update({k: j2_render_dict(v, data)})
        if isinstance(v, list):
            r.update({k: j2_render_list(v, data)})
        elif isinstance(v, str):
            # TODO j2 always returns a unicode (str) - want to be able to get complex types like in Ansible!
            r.update({k: jinja2.Environment(loader=jinja2.BaseLoader, undefined=jinja2.StrictUndefined).from_string(v).render(data)})
        else:
            r.update({k: v})
    return r

def j2_render_list(l, data):
    r = [];
    for v in l:
        if isinstance(v, dict):
            r.append(j2_render_dict(v, data))
        if isinstance(v, list):
            r.append(j2_render_list(v, data))
        elif isinstance(v, str):
            # TODO j2 always returns a unicode (str) - want to be able to get complex types like in Ansible!
            r.append(jinja2.Environment(loader=jinja2.BaseLoader, undefined=jinja2.StrictUndefined).from_string(v).render(data))
        else:
            r.append(v)
    return r

def abort(msg):
    print('Content-Type: text/plain\n')
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

conf_file = 'cgi.yml'

try:
    conf = yaml.load(open(os.path.join(cwd, conf_file)))
except yaml.YAMLError as e:
    abort('Error in config file %s' % e)
except:
    abort('Error: Could not read config file %s' % os.path.join(cwd, conf_file))

# Allow relative paths
for dir in ['bootlink_dir', 'inventory_dir', 'template_dir', 'binary_dir', 'vars_dir', 'defaults']:
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
    inventory = ansible_inventory(conf['inventory_dir'], hostname)
except KeyError as e:
    abort('Error: %s' % e)
except Exception as e:
    abort('Error in Ansible: %s' % e)

#
# Collect and render variables
#

data = {}

# Get server data
data.update({
    'os_name': os_name,
    'os_version': os_version,
    'filename': filename,
    'hostname': hostname,
})

# Get and render defaults (content)
if os.path.exists(conf['defaults']):
    try:
        data.update(j2_render_dict(yaml.load(open(conf['defaults'])), data))
    except yaml.YAMLError as e:
        abort('Error in %s: %s' % (conf['defaults'], e))
    except jinja2.TemplateError as e:
        abort('Template error in %s: %s\n \n%s' % (conf['defaults'], e, traceback.format_exc()))
    except:
        abort('Error: Could not read defaults file %s' % conf['defaults'])

# Add inventory (content)
data.update(inventory)

# Render vars_files (files in config)
vars_files = []
try:
    vars_files = j2_render_list(conf['vars_files'], data)
except jinja2.TemplateError as e:
    abort('Template error in vars_files (%s): %s\n \n%s' % (conf_file, e, traceback.format_exc()))

# Get and render vars_files (content)
for file in vars_files:
    if os.path.exists(os.path.join(conf['vars_dir'], file)):
        try:
            data.update(j2_render_dict(yaml.load(open(os.path.join(conf['vars_dir'], file))), data))
        except yaml.YAMLError as e:
            abort('Error in %s: %s' % (os.path.join(conf['vars_dir'], file), e))
        except jinja2.TemplateError as e:
            abort('Template error in %s: %s\n \n%s' % (file, e, traceback.format_exc()))
        except:
            abort('Error: Could not read vars file %s' % os.path.join(conf['vars_dir'], file))

# Render template_files (files in config)
template_files = []
try:
    template_files = j2_render_list(conf['template_files'], data)
except jinja2.TemplateError as e:
    abort('Template error in template_files (%s): %s\n \n%s' % (conf_file, e, traceback.format_exc()))

# Render binary_files (files in config)
binary_files = []
try:
    binary_files = j2_render_list(conf['binary_files'], data)
except jinja2.TemplateError as e:
    abort('Template error in binary_files (%s): %s\n \n%s' % (conf_file, e, traceback.format_exc()))

# Find template
template = ''
for file in template_files:
    if os.path.exists(os.path.join(conf['template_dir'], file)):
        template = file
        break

if template != '':
    
    #
    # Load template
    #
    
    # Add template data
    data.update({
        'template': template,
        'vars_files': vars_files,
        'template_files': template_files,
        'binary_files': binary_files,
        'template_dir': conf['template_dir'],
        'binary_dir': conf['binary_dir'],
        'vars_dir': conf['vars_dir'],
        'defaults': conf['defaults'],
        'date': datetime.datetime.today().strftime('%Y-%m-%d'),
        'time': datetime.datetime.today().strftime('%H:%M:%S'),
        # Update webserver variables here to make sure they cannot be overridden!
        'os_name': os_name,
        'os_version': os_version,
        'filename': filename,
        'hostname': hostname,
    })
    
    try:
        tpl = jinja2.Environment(
            loader=jinja2.FileSystemLoader(conf['template_dir']),
            trim_blocks=True,
            undefined=jinja2.StrictUndefined
        ).get_template(template)

        print('Content-Type: text/plain\n')
        print(tpl.render(data))
    except Exception as e:
        abort('Template error in %s: %s\n \n%s' % (template, e, traceback.format_exc()))

else:

    # Find binary file
    binary = ''
    for file in binary_files:
        if os.path.exists(os.path.join(conf['binary_dir'], file)):
            binary = os.path.join(conf['binary_dir'], file)
            break

    if binary != '':

        #
        # Deliver binary file
        #

        print('Content-Type: application/octet-stream\n')
        sys.stdout.write(open(binary,"rb").read())

    else:

        #
        # No template or binary found!
        #

        abort('Error: No template or binary found')
