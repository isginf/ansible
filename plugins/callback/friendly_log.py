# Copyright: (c) 2018, Manuel Maestinger <manuel.maestinger@inf.ethz.ch>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
  callback: friendly_log
  type: notification
  author: Manuel Maestinger <manuel.maestinger@inf.ethz.ch>
  version_added: "2.6"
  short_description: writes human- and grep-friendly log files
  description:
    - This callback writes a human- and grep-friendly log file.
    - It also maintains a change log for all file system changes done with known modules.
    - IMPORTANT: It only works for single host executions (in ansible pull mode)!
  requirements:
    - whitelisting in configuration
    - a writable LOGFILE and CHANGELOGFILE by the user executing Ansible
  options:
    logfile:
      description: Log file location
      ini:
        - section: callback_friendly_log
          key: logfile
          version_added: "2.6"
      default: /var/log/ansible.log
    logrelative:
      description: Use relative paths in log file
      ini:
        - section: callback_friendly_log
          key: logrelative
          version_added: "2.6"
      default: true
    changelogfile:
      description: Log file location for file system change log
      ini:
        - section: callback_friendly_log
          key: changelogfile
          version_added: "2.6"
      default: /var/log/ansible.changelog
    changelogdump:
      description: Dump file location for result objects of undefined modules
      ini:
        - section: callback_friendly_log
          key: changelogdump
          version_added: "2.6"
      default: /tmp/ansible.changedump
'''

#
# The following list of modules describes where to find the
# path of file system changes in the object that Ansible
# returns after executing a task. Unfortunately, every module
# differs a bit from each other.
#
# NOTE: Every found value of the defined keys will be logged to
# CHANGELOGFILE, but there is no error message if one or even
# all don't exist.
#
# If a task executes a module which is not in the list below,
# we dump the complete object to CHANGELOGDUMP. So make sure to
# add all modules you use. If you don't want to log their changes,
# just define an empty array with keys to print.
#

MODULES = '''
  template:
    - result: dest
      prepend: +
  copy:
    - result: dest
      prepend: +
  assemble:
    - result: dest
      prepend: +
  file:
    - result: path
      prepend: +
      when:
        - result: invocation.module_args.state
          matches: (directory|file|hard|link|touch)
    - result: path
      prepend: "-"
      when:
        - result: invocation.module_args.state
          matches: (absent)
  command:
    - result: invocation.module_args.creates
      prepend: +
    - result: invocation.module_args.removes
      prepend: "-"
    - result: cmd
      join: " "
      prepend: "# command: "
      when:
        - result: invocation.module_args.creates
          count: 0
        - result: invocation.module_args.removes
          count: 0
  shell:
    - result: invocation.module_args.creates
      prepend: +
    - result: invocation.module_args.removes
      prepend: "-"
    - result: cmd
      join: " "
      prepend: "# shell: "
      when:
        - result: invocation.module_args.creates
          count: 0
        - result: invocation.module_args.removes
          count: 0
  alternatives:
    - result: invocation.module_args.name
      prepend: +/etc/alternatives/
  apt:
    - result: invocation.module_args.name
      prepend: "# apt: install "
      when:
        - result: invocation.module_args.state
          matches: (latest|present)
    - result: invocation.module_args.name
      prepend: "# apt: remove "
      when:
        - result: invocation.module_args.state
          matches: (absent)
  apt_key:
    - result: invocation.module_args.keyring
      prepend: +
  apt_repository:
    - result: invocation.module_args.filename
      prepend: +/etc/apt/sources.list.d/
      append: .list
  systemd:
    - result: invocation.module_args.name
      prepend: "# systemd: "
  group:
    - result: name
      prepend: "+/etc/group # "
  member:
    - result: group
      prepend: "+/etc/group # "
'''

from ansible.module_utils._text import to_bytes
from ansible.plugins.callback import CallbackBase
import time, yaml, os, re

class ChangeLogger(object):

    '''Custom class to extract essence of changes and log it'''

    def __init__(self, logfile, dumpfile):
        self._logfile = logfile
        self._dumpfile = dumpfile
        self._modules = yaml.load(MODULES)

    def log(self, result):
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        module = result._task.serialize()['action']

        with open(self._logfile, 'ab') as fd:
            if self.is_defined(module):
                # Log changes
                for change in self.get_changes(module, result._result):
                    fd.write(to_bytes(u"[%s] %s\n" % (now, change)))
            else:
                # Log info and dumpfile
                msg = "# no definition for module '%s', see %s" % (module, self._dumpfile)
                fd.write(to_bytes(u"[%s] %s\n" % (now, msg)))

        if not self.is_defined(module):
            with open(self._dumpfile, 'ab') as fd:
                # Dump into dumpfile
                dump = yaml.dump(result._result)
                msg = "RESULT DUMP OF MODULE '%s':\n%s" % (module, dump)
                fd.write(to_bytes(u"[%s] %s\n" % (now, msg)))

    def is_defined(self, module):
        if module not in self._modules:
            return False
        for m in self._modules[module]:
            if not 'result' in m:
                return False
        return True

    def get_changes(self, module, result):
        ret = []
        for params in self._modules[module]:
            results = self._get_values(result, params['result'])
            if 'when' in params:
                if not self._apply_when(result, params['when']):
                    continue # skip this result
            if 'join' in params:
                results = [params['join'].join(results)]
            for r in results:
                ret.append(self._format(str(r), params))
        return ret

    def _get_values(self, obj, key, remove_none = True):
        prev = obj
        keys = key.split('.')
        for i, k in enumerate(keys):
            if k not in prev:
                break
            prev = prev[k]
            if i == (len(keys) - 1):
                if not isinstance(prev, list):
                    prev = [prev]
                return self._remove_none(prev) if remove_none else prev
        return []

    def _remove_none(self, data):
        return [d for d in data if d is not None]

    def _apply_when(self, result, whens):
        ret = True
        for when in whens:
            if not 'result' in when:
                continue # skip this condition
            res = self._get_values(result, when['result'])

            if 'matches' in when:
                if len(res) != 1 or not re.match(when['matches'], res[0]):
                    ret = False
            elif 'contains' in when:
                if not when['contains'] in res:
                    ret = False
            elif 'count' in when:
                if len(res) != when['count']:
                    ret = False
            else:
                continue # skip this condition
        return ret
    
    def _format(self, value, params):
        if 'prepend' in params:
            value = params['prepend'] + value
        if 'append' in params:
            value = value + params['append']
        return value


class CallbackModule(CallbackBase):

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'friendly_log'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self, display=None):
        super(CallbackModule, self).__init__(display=display)

    def set_options(self, task_keys=None, var_options=None, direct=None):
        super(CallbackModule, self).set_options(task_keys=task_keys, var_options=var_options, direct=direct)
        self._logfile = self.get_option('logfile')
        self._changelogger = ChangeLogger(
            self.get_option('changelogfile'),
            self.get_option('changelogdump')
        )

        if isinstance(self.get_option('logrelative'), bool):
            self._logrelative = self.get_option('logrelative')
        else:
            self._logrelative = (self.get_option('logrelative') in ['true', 'True', 'TRUE', 'yes', 'Yes', 'YES', '1'])

    def _log(self, status, message):
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        status = status.upper().ljust(13)

        with open(self._logfile, 'ab') as fd:
            fd.write(to_bytes(u"[%s] %s %s\n" % (now, status, message)))

    def _log_task(self, status, result):
        path = result._task.get_path()
        if self._logrelative and path.startswith(self._playbook_path):
            path = path[(len(self._playbook_path)+1):]

        task = result._task.get_name().strip().split(" : ", 1)[-1]

        log = "at %s (%s)" % (path, task)
        # add item when in loop
        item = self._get_item_label(result._result)
        if item is not None:
            log += " with item %s" % item
        # add message if exists (e.g. on fail)
        if 'msg' in result._result:
            log += ": %s" % result._result['msg']
        elif 'message' in result._result:
            log += ": %s" % result._result['message']
        self._log("task %s" % status, log)

        # do status specific stuff
        if status == "changed":
            self._changelogger.log(result)

    #
    # Overwrite plugin functions
    #

    def v2_playbook_on_start(self, playbook):
        self._playbook_path = os.path.dirname(playbook._file_name)
        self._playbook_file = os.path.basename(playbook._file_name)
        path = self._playbook_file if self._logrelative else playbook._file_name
        self._log("playbook", "at %s %s" % (path, "".rjust(75, "#")))

    def v2_playbook_on_play_start(self, play):
        path = self._playbook_file if self._logrelative else os.path.join(self._playbook_path, self._playbook_file)
        self._log("play start", "at %s (%s)" % (path, play.get_name().strip()))

    def v2_playbook_on_stats(self, stats):
        t = stats.summarize(stats.processed.keys()[0])
        self._log("play end", ", ".join("%s=%r" % (key,val) for (key,val) in t.iteritems()))

    def v2_runner_on_failed(self, result, ignore_errors=False):
       if not result._task.loop:
           self._log_task("failed", result)

    def v2_runner_on_ok(self, result):
        if not result._task.loop:
            self._log_task("changed" if result._result.get("changed", False) else "ok", result)

    def v2_runner_on_skipped(self, result):
        self._log_task("skipped", result)

    def v2_runner_on_unreachable(self, result):
        self._log("skipped", "host %s is unreachable" % result._host.get_name())

    def v2_playbook_on_no_hosts_matched(self):
        self._log("skipped", "no hosts matched")

    def v2_runner_item_on_ok(self, result):
        self._log_task("changed" if result._result.get("changed", False) else "ok", result)

    def v2_runner_item_on_failed(self, result):
        self._log_task("failed", result)

    def v2_runner_item_on_skipped(self, result):
        self._log_task("skipped", result)

    def v2_on_file_diff(self, result):
        pass # will not happen with ansible pull

    def v2_playbook_on_cleanup_task_start(self, task):
        pass # nothing to log (we log tasks already)

    def v2_playbook_on_handler_task_start(self, task):
        pass # nothing to log (we log tasks already)

    def v2_playbook_on_import_for_host(self, result, imported_file):
        pass # will not happen with ansible pull

    def v2_playbook_on_include(self, included_file):
        pass # nothing to log

    def v2_playbook_on_no_hosts_remaining(self):
        pass # nothing to log

    def v2_playbook_on_notify(self, handler, host):
        pass # nothing to log (handlers should be sufficient)

    def v2_playbook_on_not_import_for_host(self, result, missing_file):
        pass # will not happen with ansible pull

    def v2_playbook_on_task_start(self, task, is_conditional):
        pass # nothing to log (we log at result only)

    def v2_playbook_on_vars_prompt(self, varname, private=True, prompt=None, encrypt=None, confirm=False, salt_size=None, salt=None, default=None):
        pass # will not happen with ansible pull

    def v2_runner_on_async_failed(self, result):
        pass # will not happen with ansible pull

    def v2_runner_on_async_ok(self, result):
        pass # will not happen with ansible pull

    def v2_runner_on_async_poll(self, result):
        pass # will not happen with ansible pull

    def v2_runner_retry(self, result):
        pass # will (most likely) not happen with ansible pull (usually used for polling other hosts)

