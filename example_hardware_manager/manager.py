# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


from ironic_python_agent import errors
from ironic_python_agent import hardware


class ExampleHardwareManager(hardware.HardwareManager):
    """Example Hardware Manager"""

    HARDWARE_MANAGER_NAME = 'ExampleHardwareManager'
    HARDWARE_MANAGER_VERSION = '1'

    def evaluate_hardware_support(self):
        """Declare whether the system is supported by this manager.

        :returns: HardwareSupport level for this manager.
        """
        # This should work for anything which supports dmidecode
        return hardware.HardwareSupport.SERVICE_PROVIDER

    def get_clean_steps(self, node, _ports):
        """Get a list of clean steps with priority.

        :param node: The node object as provided by Ironic.
        :param ports: Port objects as provided by Ironic.
        :returns: A list of cleaning steps, as a list of dicts.
        """
        return [{'step': 'example_step',
                 'priority': 90,
                 'interface': 'deploy',
                 'reboot_requested': False,
                 'abortable': True}]

    def example_step(self, node, _ports):
        fail_msg = node['extra'].get('example_clean_step_msg')
        if fail_msg:
            raise errors.CleaningError(fail_msg)
        return True
