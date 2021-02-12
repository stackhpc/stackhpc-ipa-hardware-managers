# Copyright 2015 Rackspace, Inc.
# Copyright 2018 StackHPC Ltd.
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

import glob
import itertools
import os
from collections import namedtuple

from ironic_python_agent import errors
from ironic_python_agent import hardware
from ironic_python_agent import utils

from oslo_concurrency import processutils
from oslo_log import log
from oslo_utils import strutils

_MATCHING_RULE_FAILED_SUMMARY_MSG_TEMPLATE = (
    "When verifying NIC firmware, {failures} matching rule(s) failed "
    "to produce a match. \n"
)
_MISSING_MATCHER_RULE = (
    "Not checking NIC firmware for {interface}. "
    "There was no rule for pci_id: {pci_id} set in "
    "nic_firmware property"
)
_DUPLICATE_ENTRIES_MSG_TEMPLATE = (
    "Multiple matchers with the same pci_id. The conflict "
    "occured for pci_id: {pci_id}. Using "
    "firmware_version: {new} instead of {old}"
)
_FIRMWARE_CHECK_DISABLE_KEY = 'disable_nic_firmware_check'
_HELP_MSG_EXAMPLE = (
    "For cleaning to proceed, you must set the property "
    "'nic_firmware' in the node's extra field, for example:\n"
    "$ openstack baremetal node set $NODE_ID --extra "
    """nic_firmware='[{"vendor_id": "15B3","device_id": " "1013","""
    """firmware_version": "12.20.1019"}]'"""
)

LOG = log.getLogger()


def _get_base_in_relative_path(path):
    # given relative path, returns the base element, e.g one/two/three,
    # returns one
    if os.path.isabs(path):
        raise ValueError("path must be relative")
    return path.split(os.sep)[0]


def _parse_uevent(interface_line_pairs):
    # converts the contents of /sys/class/net/*/device/uevent into a dictionary
    # The name in the wild card position becomes the key and contents of uevent
    # is itself mapped to a dictionary.
    #
    # the uevent dictionary maps the component before the first equals sign to
    # to the component after e.g given PCI_SLOT_NAME=0000:00:19.0\n,
    # the dictionary will contain: {"PCI_SLOT_NAME" : "0000:00:19.0"}
    result = {}
    for interface, line in interface_line_pairs:
        remaining_chars = iter(line.rstrip())
        if interface not in result:
            result[interface] = {}
        split = itertools.takewhile(lambda x: x != "=", remaining_chars)
        key = "".join(split)
        value = "".join(remaining_chars)
        result[interface][key] = value
    return result


def _get_uevent_devices():
    for uevent_file in glob.glob("/sys/class/net/*/device/uevent"):
        yield (_get_NIC_name(uevent_file), uevent_file)


def _get_devices():
    for device, _ in _get_uevent_devices():
        yield device


def _uevent_lines():
    for interface_name, uevent_file in _get_uevent_devices():
        with open(uevent_file, "r") as f:
            for line in f.readlines():
                yield (interface_name, line)


def _get_pci_id(uevent_mapping):
    # extracts pci id from uevent dictionary
    return _parse_pci_id(uevent_mapping["PCI_ID"])


def _get_pci_id_from_matcher(matcher):
    device_id = _get_expected_field(matcher, "device_id")
    vendor_id = _get_expected_field(matcher, "vendor_id")
    return (vendor_id, device_id)


def _get_pci_id_lookup_table(firmware_matchers):
    # pci_id to firmware matching rule
    result = {}
    for matcher in firmware_matchers:
        version = _get_expected_field(matcher, "firmware_version")
        pci_id = _get_pci_id_from_matcher(matcher)
        if pci_id in result:
            LOG.warning(_DUPLICATE_ENTRIES_MSG_TEMPLATE
                        .format(pci_id=pci_id, new=version,
                                old=result[pci_id]["firmware_version"]))
        result[pci_id] = matcher
    return result


def _parse_pci_id(id):
    # parses a pci_id in the form "vendor_id:device_id"
    result = tuple(id.strip().split(":"))
    if len(result) != 2:
        raise ValueError("pci id is expected to be in the form: "
                         "'vendor_id:device_id'")
    try:
        int(result[0], 16)
        int(result[1], 16)
    except (ValueError):
        raise ValueError("Both vendor_id and device_id are expected to be "
                         "strings representing hexadecimal numbers")
    return result


def _get_NIC_name(uevent_file):
    # network card name appears in wildcard position of the
    # /sys/class/net/*/device/uevent glob
    relative_path = os.path.relpath(uevent_file, "/sys/class/net/")
    return _get_base_in_relative_path(relative_path)


def _get_ethtool_output(dev, **kwargs):
    kwargs["shell"] = True
    try:
        ethtool_output, _e = utils.execute(
            "ethtool -i {device}".format(device=dev),
            **kwargs)
    except (processutils.ProcessExecutionError, OSError) as e:
        raise errors.CleaningError(
            "The command: ethtool failed to execute when performing NIC "
            "firmware check. {}".format(e)
        )
    return ethtool_output


def _get_ethtool_field(ethtool_output, field):
    # given the example ethtool_output:
    #
    #   driver: mlx5_core
    #   version: 3.0-1 (January 2015)
    #   firmware-version: 12.20.1010
    #   expansion-rom-version:
    #   bus-info: 0000:03:00.1
    #   supports-statistics: yes
    #   supports-test: yes
    #   supports-eeprom-access: no
    #   supports-register-dump: no
    #   supports-priv-flags: yes
    #
    # the available fields are driver, version, firmware-version, etc.
    for line in ethtool_output.splitlines():
        (candidate_field, value) = tuple(line.split(": "))
        if candidate_field == field:
            return value


def _get_expected_field(firmware_matcher, field):
    try:
        value = firmware_matcher[field]
    except KeyError:
        raise errors.CleaningError(
            "Expected field '{0}' not found. You should make sure all items"
            " in the nic_firmware list contain the field: {0}".format(field))
    return value


def _is_nic_verification_disabled(node):
    disable_check = node['extra'].get(_FIRMWARE_CHECK_DISABLE_KEY)
    return strutils.bool_from_string(
        disable_check) if disable_check is not None else False


def _matcher_to_hashable(matcher):
    # we use a frozen set of key-value pairs so that the matchers are
    # hashable, but in the future, if firmware-versions is made into a list
    # we will have to convert that to a frozenset as well
    return frozenset(matcher.iteritems())


def _hashable_matcher_to_err_msg(matcher):
    return ("The following NIC firmware matcher failed to match: {}"
            .format(dict(matcher)))


NICFirmwareVerifyResult = namedtuple(
    'NICFirmwareVerifyResult',
    'actual_version expected_version '
    'matcher')

NICDescriptor = namedtuple('NICDescriptor', "name pci_id firmware_version")


class SystemNICHardwareManager(hardware.HardwareManager):
    """Checks firmware version for a given network card"""

    HARDWARE_MANAGER_VERSION = "1.0"

    def evaluate_hardware_support(self):
        """Declare whether the system is supported by this manager.

        :returns: HardwareSupport level for this manager.
        """
        # This should work for anything which supports ethtool
        return hardware.HardwareSupport.SERVICE_PROVIDER

    def get_clean_steps(self, node, ports):
        """Get a list of clean steps with priority.

        :param node: The node object as provided by Ironic.
        :param ports: Port objects as provided by Ironic.
        :returns: A list of cleaning steps, as a list of dicts.
        """
        return [{'step': 'verify_nic_firmware',
                 'priority': 90,
                 'interface': 'deploy',
                 'reboot_requested': False,
                 'abortable': True}]

    def get_interface_descriptors(self):
        """Enumerate all interfaces as NicDescriptor objects

        :return: list of NicDescriptor
        """
        # there might be multiple identical cards, we must check them all
        uevent_mappings = _parse_uevent(_uevent_lines())
        result = []
        for interface, uevent_device_info in uevent_mappings.iteritems():
            pci_id = _get_pci_id(uevent_device_info)
            ethtool_output = _get_ethtool_output(interface)
            firmware = _get_ethtool_field(ethtool_output, "firmware-version")
            result.append(NICDescriptor(pci_id=pci_id, name=interface,
                                        firmware_version=firmware))
        return result

    def verify_nic_firmware(self, node, ports):
        """
        Verify all firmware versions specified by the nic_firmware property.

        The nic_firmware property should take the form of a json list of
        firmware matching criteria. The firmware matching criteria should
        be a dictionary containing the following required fields:

        - vendor_id : numeric pci vendor id
        - device_id : numeric pci device id
        - firmware_version : expected firmware version

        the values of all fields should be strings. An example is given below::

            [
                { "vendor_id": "15B3", "device_id": "1013",
                  "firmware_version": "12.20.1010" }
            ]

        The nic_firmware property can be manually set on a given node, as shown
        in this example::

              openstack baremetal node set $NODE_ID --extra \\
              nic_firmware='[{"vendor_id": "15B3", "device_id": "1013", \\
              "firmware_version": "12.20.1010"}]'

        Each network card is checked against each of the items in the matching
        criteria list. If the device and vendor ids match, the firmware version
        is checked against the expected version specified in the
        nic_firmware property's firmware_version field.

        """

        if _is_nic_verification_disabled(node):
            LOG.warning('NIC firmware version verification has been disabled.')
            return {}

        if "extra" not in node or "nic_firmware" not in node["extra"]:
            raise errors.CleaningError(
                "Expected property 'nic_firmware' not found. " +
                _HELP_MSG_EXAMPLE)

        firmware_matchers = node["extra"]["nic_firmware"]

        if not isinstance(firmware_matchers, list):
            raise errors.CleaningError(
                "The property 'nic_firmware' should be a list. " +
                _HELP_MSG_EXAMPLE
            )

        lookup_table = _get_pci_id_lookup_table(firmware_matchers)
        successes, failures = self._process_expected_versions(lookup_table)

        error_msgs = []
        for interface, result in failures.iteritems():
            msg = (
                "Firmware version mismatch for card: {interface}. The "
                "expected version was: {expected_version}, "
                "but the actual version was {actual_version}. "
                "The matcher that failed was {matcher}"
            ).format(
                interface=interface,
                expected_version=result.expected_version,
                actual_version=result.actual_version,
                matcher=result.matcher)
            error_msgs.append(msg)

        if failures:
            raise errors.CleaningError(
                "Found {} firmware version mismatches "
                "when verifying NIC firmware. The errors were: \n"
                .format(len(error_msgs)) +
                "\n".join(error_msgs)
            )

        self._verify_all_rules_matched(firmware_matchers, successes)

        return successes

    @staticmethod
    def _verify_all_rules_matched(firmware_matchers, successes):
        successful_matchers = map(
            lambda x: _matcher_to_hashable(x.matcher),
            successes.itervalues()
        )
        all_matchers = map(
            lambda x: _matcher_to_hashable(x),
            firmware_matchers
        )
        non_matching = set(all_matchers) - set(successful_matchers)
        if non_matching:
            raise errors.CleaningError(
                _MATCHING_RULE_FAILED_SUMMARY_MSG_TEMPLATE
                .format(failures=len(non_matching)) +
                "\n".join(map(_hashable_matcher_to_err_msg, non_matching))
            )

    def _process_expected_versions(self, pci_matcher_lookup_table):
        """Processes all matching rules

        where a matching rule is a dict with the following required fields:

        * vendor_id : a numeric pci vendor id
        * device_id: a numeric pci device id
        * firmware_version: expected firmware version

        :param pci_matcher_lookup_table: dictionary mapping pci_id to a
            matching rule
        :return: tuple with the structure (successes, failures) where,
            *successes* and *failures* are dictionaries mapping the
            interface name to a NICFirmwareVerifyResult
        """

        interfaces = self.get_interface_descriptors()
        assert type(interfaces) == list
        successes = {}
        failures = {}
        for interface in interfaces:
            actual_version = interface.firmware_version
            interface_name = interface.name
            pci_id = interface.pci_id
            if pci_id not in pci_matcher_lookup_table:
                LOG.warning(_MISSING_MATCHER_RULE
                            .format(interface=interface_name, pci_id=pci_id))
                continue
            matcher = pci_matcher_lookup_table[pci_id]
            expected_version = matcher["firmware_version"]
            if actual_version == expected_version:
                LOG.debug("firmware version matches for interface: {}".format(
                    interface_name))
                successes[interface_name] = NICFirmwareVerifyResult(
                    actual_version,
                    expected_version,
                    matcher
                )
            else:
                failures[interface_name] = NICFirmwareVerifyResult(
                    actual_version,
                    expected_version,
                    matcher
                )
        return (successes, failures)
