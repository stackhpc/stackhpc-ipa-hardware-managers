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
from oslo_utils import strutils


LOG = log.getLogger()


def _get_property(dmidecode_property):
    system_property = ''
    try:
        system_property, _e = utils.execute(
            "sudo dmidecode -s {}".format(dmidecode_property),
            shell=True)
    except (processutils.ProcessExecutionError, OSError) as e:
        LOG.warning("Cannot read system property: {}".format(e))

    system_property = system_property.rstrip()
    LOG.debug('System property: {}'.format(system_property))
    return system_property


def _get_bios():
    return _get_property('bios-version')


def _handle_bios_update(actual_bios_version, expected_bios_version):
    """Handle system BIOS update stub.

    Future managers may override this to support automatic updates.
    """
    raise errors.CleaningError(
        "A manual BIOS update is required. Expected version '{0}' but "
        "version '{1}' was installed".
        format(expected_bios_version, actual_bios_version))


def _get_expected_property(node, node_property):
    try:
        expected_property = node['extra']['system_vendor'][node_property]
    except KeyError as e:
        raise errors.CleaningError(
            "Expected property '{0}' not found. For cleaning to proceed "
            "you must set the property 'system_vendor/{1}' in the node's "
            "extra field, for example: $ openstack baremetal node set "
            "$NODE_ID --extra system_vendor/{1}=$VALUE".format(e.message,
                                                               node_property))
    return expected_property


def _bios_verification_disabled(node):
    disable_check = node['extra'].get('disable_bios_version_check')
    return strutils.bool_from_string(
        disable_check) if disable_check is not None else False


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
        """Verify the BIOS version.

        To avoid the case where two different products may have the same BIOS
        version, we also check that the product is as expected.
        """
        if _bios_verification_disabled(node):
            LOG.warning('BIOS version verification has been disabled.')
            return True

        vendor_info = hardware.dispatch_to_managers('get_system_vendor_info')

        expected_product_name = _get_expected_property(node, 'product_name')
        actual_product_name = vendor_info.product_name
        product_match = expected_product_name == actual_product_name

        expected_bios_version = _get_expected_property(node, 'bios_version')
        actual_bios_version = _get_bios()
        bios_version_match = expected_bios_version == actual_bios_version

        if product_match and bios_version_match:
            LOG.debug('Specified product and BIOS version match; '
                      'no update is required.')
            return True
        elif product_match:
            LOG.debug('BIOS version did not match; attempting an update.')
            try:
                _handle_bios_update(actual_bios_version, expected_bios_version)
            except Exception as e:
                # Log and pass through the exception so cleaning will fail
                LOG.exception(e)
                raise
            return True
        else:
            raise errors.CleaningError(
                "Product did not match. Expected product '{0}', but the "
                "actual product is '{1}'. Check that the product set in the "
                "node's extra field under 'system_vendor/product' matches "
                "the actual product.".format(expected_product_name,
                                             actual_product_name))
