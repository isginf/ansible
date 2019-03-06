# Copyright: (c) 2019, Manuel Maestinger <manuel.maestinger@inf.ethz.ch>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}


def reverse_format(string, pattern):
    return pattern % string


# ---- Ansible filters ----
class FilterModule(object):
    def filters(self):
        return {
            'rformat': reverse_format,
        }
