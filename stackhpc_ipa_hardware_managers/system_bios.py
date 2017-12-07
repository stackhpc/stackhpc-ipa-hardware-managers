# Copyright 2015 Rackspace, Inc.
# Copyright 2017 StackHPC Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ironic_python_agent import errors
from ironic_python_agent import hardware
from ironic_python_agent import utils

from oslo_concurrency import processutils

from oslo_log import log

LOG = log.getLogger()

_PRODUCT_MISMATCH = ("The product name specified in the node properties does "
                     "not match the server.")
_MANUAL_UPDATE_REQUIRED = ("Automatic BIOS update is not implemented; "
                           "a manual update is required.")


def _is_property(dmidecode_property, expected_property):
    """Check if a system property matches a particular value."""
    system_property = None
    try:
        system_property, _e = utils.execute(
            "sudo dmidecode -s {}".format(dmidecode_property),
            shell=True)
    except (processutils.ProcessExecutionError, OSError) as e:
            LOG.warning("Cannot read system property: {}".format(e))

    system_property = system_property.rstrip()
    LOG.debug('System property: {}'.format(system_property))
    return True if system_property == expected_property else False


def _is_product(expected_product_name):
    return _is_property('system-product-name',
                        expected_product_name)


def _is_bios(expected_bios_version):
    return _is_property('bios-version',
                        expected_bios_version)


def _update_bios():
    """Update system BIOS.

    Future managers may override this to support their particular hardware.
    """
    raise errors.CleaningError(_MANUAL_UPDATE_REQUIRED)


def _get_expected_property(node, property):
    try:
        expected_property = node['extra']['system_vendor'][property]
    except KeyError as e:
        raise errors.CleaningError("Expected property not found. For "
                                   "cleaning to pass you must set the "
                                   "property name: {}".format(e))
    return expected_property


class SystemBiosHardwareManager(hardware.HardwareManager):
    """Generic system BIOS manager"""

    HARDWARE_MANAGER_NAME = 'SystemBiosHardwareManager'
    HARDWARE_MANAGER_VERSION = '1'

    def evaluate_hardware_support(self):
        """Declare whether the system is supported by this manager.

        :returns: HardwareSupport level for this manager.
        """
        # This should work for anything which supports dmidecode
        return hardware.HardwareSupport.SERVICE_PROVIDER

    def get_clean_steps(self, node, ports):
        """Get a list of clean steps with priority.

        :param node: The node object as provided by Ironic.
        :param ports: Port objects as provided by Ironic.
        :returns: A list of cleaning steps, as a list of dicts.
        """
        return [{'step': 'verify_bios_version',
                 'priority': 90,
                 'interface': 'deploy',
                 'reboot_requested': False,
                 'abortable': True}]

    def verify_bios_version(self, node, ports):
        """Verify the BIOS version"""
        expected_product_name = _get_expected_property(node, 'product_name')
        product_match = _is_product(expected_product_name)

        expected_bios_version = _get_expected_property(node, 'bios_version')
        bios_version_match = _is_bios(expected_bios_version)

        if product_match and bios_version_match:
            LOG.debug('Specified product and BIOS version match; '
                      'no update is required.')
            return True
        elif product_match:
            LOG.debug('BIOS version did not match; attempting an update.')
            try:
                _update_bios()
            except Exception as e:
                # Log and pass through the exception so cleaning will fail
                LOG.exception(e)
                raise
            return True
        else:
            raise errors.CleaningError(_PRODUCT_MISMATCH)
