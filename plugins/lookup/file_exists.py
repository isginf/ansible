# Copyright: (c) 2018, Manuel Maestinger <manuel.maestinger@inf.ethz.ch>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
  lookup: file_exists
  author: Manuel Maestinger <manuel.maestinger@inf.ethz.ch>
  version_added: "2.6"
  short_description: test if file exists
  description:
    - This lookup tests if a file exists in the task's expected search path.
  options:
    _terms:
      description: file with relative or absolute path to test
      required: True
'''

EXAMPLES = '''
- name: include all vars files if they exist
  include_vars: "{{ item }}"
  when: lookup('file_exists', 'vars/' ~ item)
  loop:
    - "{{ ansible_fqdn }}.yml"
    - "{{ ansible_distribution ~ '_' ~ ansible_distribution_version }}.yml"
    - "{{ ansible_distribution }}.yml"
    - "All.yml"
'''

RETURN = '''
  _raw:
    description:
      - boolean if file exists or not
'''

from ansible.plugins.lookup import LookupBase

class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        ret = []
        for term in terms:
            lookup = self.find_file_in_search_path(variables, ".", term, ignore_missing=True)
            ret.append(lookup is not None)
        return ret
