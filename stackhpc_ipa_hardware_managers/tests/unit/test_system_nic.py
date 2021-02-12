# Copyright (c) 2018 StackHPC Ltd.
#
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

import os
import re
import unittest

from ironic_python_agent import errors
from ironic_python_agent import hardware

import mock

from stackhpc_ipa_hardware_managers import system_nic

EXPECTED_VERSION = "12.20.1010"

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


def get_dummy_node_info(version=EXPECTED_VERSION, disable='false'):
    return {
        'extra': {
            system_nic._FIRMWARE_CHECK_DISABLE_KEY: disable,
            'nic_firmware': [
                get_dummy_nic_matcher(version=version)
            ]
        }
    }


def get_dummy_nic_matcher(vendor='15B3', device='1013',
                          version=EXPECTED_VERSION):
    return {
        'vendor_id': vendor,
        'device_id': device,
        'firmware_version': version
    }


def get_dummy_node_info_not_list():
    return {
        'extra': {
            system_nic._FIRMWARE_CHECK_DISABLE_KEY: False,
            'nic_firmware': get_dummy_nic_matcher()
        }
    }


EXPECTED_UEVENT_PARSE_RESULT = {
    'enp3s0': {
        'PCI_CLASS': '20000', 'PCI_SUBSYS_ID': '15B3:0014',
        'MODALIAS': 'pci:v000015B3d00001013sv000015B3sd00000014bc02sc00i00',
        'DRIVER': 'mlx5_core', 'PCI_ID': '15B3:1013',
        'PCI_SLOT_NAME': '0000:03:00.1'}
}


def get_ethtool_output():
    with open(os.path.join(TEST_DIR, "data/ethtool.output"), "r") as f:
        return f.read()


def get_uevent_output():
    with open(os.path.join(TEST_DIR, "data/net_dev_uevent.output"), "r") as f:
        return f.read()


def get_uevent_lines():
    data = get_uevent_output()
    for line in data.splitlines():
        yield ("enp3s0", line)


class TestSystemNIC(unittest.TestCase):

    def test_parse_uevent(self):
        result = system_nic._parse_uevent(get_uevent_lines())
        self.assertEquals(EXPECTED_UEVENT_PARSE_RESULT, result)

    @mock.patch.object(system_nic.LOG, 'warning')
    def test_get_pci_id_lookup_table_override(self, mock_logger):
        # subsequent value overrides original
        newer = get_dummy_nic_matcher()
        newer["firmware_version"] = "override"
        pci_id = system_nic._get_pci_id_from_matcher(newer)
        conflict = [get_dummy_nic_matcher(), newer]
        result = system_nic._get_pci_id_lookup_table(conflict)
        expected = system_nic._DUPLICATE_ENTRIES_MSG_TEMPLATE.format(
            pci_id=pci_id, new=newer["firmware_version"], old=EXPECTED_VERSION
        )
        # we expect a warning messasge to be shown
        mock_logger.assert_any_call(expected)
        self.assertEqual(result[pci_id]["firmware_version"], "override")

    def test_get_pci_id_lookup_table(self):
        dummy = get_dummy_nic_matcher()
        pci_id = system_nic._get_pci_id_from_matcher(dummy)
        matchers = [dummy]
        result = system_nic._get_pci_id_lookup_table(matchers)
        self.assertEqual(result[pci_id]["firmware_version"], EXPECTED_VERSION)

    def test_parse_pci_id(self):
        data = "15B3:1013"
        result = system_nic._parse_pci_id(data)
        self.assertEqual(("15B3", "1013"), result)

    def test_parse_pci_id_too_many_components(self):
        data = "15B3:1013:1234"
        self.assertRaises(ValueError, system_nic._parse_pci_id, data)

    def test_parse_pci_id_non_numeric(self):
        data = "intel:r8168"
        self.assertRaises(ValueError, system_nic._parse_pci_id, data)

    def test_get_pci_id(self):
        result = system_nic._get_pci_id(EXPECTED_UEVENT_PARSE_RESULT['enp3s0'])
        self.assertEqual(("15B3", "1013"), result)

    def test_get_NIC_name(self):
        input = "/sys/class/net/enp3s0/device/uevent"
        result = system_nic._get_NIC_name(input)
        self.assertEqual("enp3s0", result)

    def test_get_ethtool_field(self):
        input = get_ethtool_output()
        result = system_nic._get_ethtool_field(input, "firmware-version")
        self.assertEqual("12.20.1010", result)


class SystemNICHardwareManagerMock(system_nic.SystemNICHardwareManager):

    def get_interface_descriptors(self):
        # generates a interface descriptor matching _get_dummy_nic_matcher()
        dummy = get_dummy_nic_matcher()
        pci_id = system_nic._get_pci_id_from_matcher(dummy)
        # name "enp3s0" is arbitrary
        return [system_nic.NICDescriptor(
            name="enp3s0", pci_id=pci_id,
            firmware_version=EXPECTED_VERSION
        )]


def generate_fake_matchers(matchers):
    return [get_dummy_nic_matcher(
        vendor=i,
        device=i + matchers,
        version="version{}".format(i)) for i in range(0, matchers)]


def generate_fake_devices(devices_per_matcher, firmwares,
                          corruptions={}):
    # generates a tuple of the form (dummy_descriptors, good_versions)
    #
    # *dummy_descriptors* is a list of system_nic.NICDescriptor. It is
    # populated by dummy devices of the form eth#, where # is an integer.
    # The number of dummy devices is set by *devices_per_matcher*
    #
    # *corruptions* is a dictionary that allows you to force the firmware
    # version of a given dummy device to one which will not match. The
    # device to be "corrupted" comes from the dictionary key, and the
    # firmware version to be set, the corresponding value.
    #
    # *good_versions* maps the interface names of all dummy devices to
    # the firmware_version to the value that would parse verification
    dummy_descriptors = []
    good_versions = {}
    i = 0
    for firmware in firmwares:
        fake_devices = []
        for _ in range(0, devices_per_matcher):
            # interface names must be unique
            fake_devices.append("eth{}".format(i))
            i += 1
        for device in fake_devices:
            good_versions[device] = firmware["firmware_version"]
            pci_id = system_nic._get_pci_id_from_matcher(firmware)
            if device in corruptions:
                dummy_descriptors.append(system_nic.NICDescriptor(
                    name=device,
                    pci_id=pci_id,
                    firmware_version=corruptions[device]
                ))
            else:
                dummy_descriptors.append(system_nic.NICDescriptor(
                    name=device,
                    pci_id=pci_id,
                    firmware_version=firmware["firmware_version"]
                ))
    return (dummy_descriptors, good_versions)


class TestSystemNICManager(unittest.TestCase):

    def setUp(self):
        self.manager = SystemNICHardwareManagerMock()

    def test_evaluate_hardware_support(self):
        actual = self.manager.evaluate_hardware_support()
        self.assertEqual(hardware.HardwareSupport.SERVICE_PROVIDER, actual)

    def test_verify_nic_firmware_disabled(self):
        for value in (True, "true", "on", "y", "yes"):
            self._verify_nic_firmware_disabled(value)

    def test_verify_nic_firmware_explicity_enabled(self):
        for value in (False, "false", "off", "n", "no"):
            node = get_dummy_node_info(disable=value)
            self._verify_nic_firmware(node)

    def test_verify_nic_firmware_enabled(self):
        node = get_dummy_node_info()
        del node['extra'][system_nic._FIRMWARE_CHECK_DISABLE_KEY]
        self._verify_nic_firmware(node)

    def _verify_nic_firmware_disabled(self, value):
        node = get_dummy_node_info(disable=value)
        self.assertFalse(self.manager.verify_nic_firmware(node, None))

    def _verify_nic_firmware(self, node):
        self.assertTrue(
            self.manager.verify_nic_firmware(
                node, None))

    def test_nic_firmware_mismatch(self):
        spoof_version = "will_not_match"
        # clearly different
        self._verify_nic_firmware_mismatch(spoof_version, EXPECTED_VERSION)

    def test_nic_firmware_substrings(self):
        spoof_version = "will_not_match"
        self._verify_nic_firmware_mismatch(
            spoof_version,
            spoof_version[1:]
        )
        self._verify_nic_firmware_mismatch(
            spoof_version,
            spoof_version[:-1]
        )

    def test_nic_firmware_appendix(self):
        spoof_version = "will_not_match"
        self._verify_nic_firmware_mismatch(
            spoof_version,
            spoof_version + "ADDITIONAL"
        )
        self._verify_nic_firmware_mismatch(
            spoof_version + "ADDITIONAL",
            spoof_version
        )

    def test_verify_missing_vendor(self):
        node = get_dummy_node_info()
        del node["extra"]["nic_firmware"][0]["vendor_id"]
        self.assertRaisesRegexp(
            errors.CleaningError,
            "vendor_id",
            self.manager.verify_nic_firmware,
            node,
            None
        )

    def test_verify_missing_device_id(self):
        node = get_dummy_node_info()
        del node["extra"]["nic_firmware"][0]["device_id"]
        self.assertRaisesRegexp(
            errors.CleaningError,
            "device_id",
            self.manager.verify_nic_firmware,
            node,
            None
        )

    def test_verify_missing_firmware_version(self):
        node = get_dummy_node_info()
        del node["extra"]["nic_firmware"][0]["firmware_version"]
        self.assertRaisesRegexp(
            errors.CleaningError,
            "firmware_version",
            self.manager.verify_nic_firmware,
            node,
            None
        )

    def test_verify_missing_nic_firmware(self):
        node = get_dummy_node_info()
        del node["extra"]["nic_firmware"]
        self.assertRaisesRegexp(
            errors.CleaningError,
            "Expected property 'nic_firmware' not found",
            self.manager.verify_nic_firmware,
            node,
            None
        )

    def test_verify_nic_firmware_not_list(self):
        node = get_dummy_node_info_not_list()
        self.assertRaisesRegexp(
            errors.CleaningError,
            "The property 'nic_firmware' should be a list",
            self.manager.verify_nic_firmware,
            node,
            None
        )

    @mock.patch.object(SystemNICHardwareManagerMock,
                       'get_interface_descriptors')
    def test_verify_nic_firmware_non_matching_rule_no_devices(
            self, mock_manager):
        # we spoof that no devices are found, all matchers fail
        mock_manager.side_effect = lambda: []
        node = get_dummy_node_info()
        self._verify_non_matching_rule(node, expected_failures=1)

    def test_verify_nic_firmware_non_matching_rule(self):
        self._verify_non_matching_rule_helper(1)
        self._verify_non_matching_rule_helper(2)
        self._verify_non_matching_rule_helper(13)

    def _verify_non_matching_rule_helper(self, failures):
        node = get_dummy_node_info()
        mismatchers = generate_fake_matchers(failures)
        matchers = [get_dummy_nic_matcher()] + mismatchers
        node["extra"]["nic_firmware"] = matchers
        self._verify_non_matching_rule(
            node,
            expected_failures=failures
        )

    def _verify_non_matching_rule(self, node, expected_failures):
        expected_msg = (system_nic._MATCHING_RULE_FAILED_SUMMARY_MSG_TEMPLATE
                        .format(failures=expected_failures)
                        )
        self.assertRaisesRegexp(
            errors.CleaningError,
            re.escape(expected_msg),
            self.manager.verify_nic_firmware,
            node,
            None
        )

    @mock.patch.object(system_nic.LOG, 'warning')
    def test_verify_nic_firmware_no_matching_rule(self, mock_logger):
        node = get_dummy_node_info()
        node["extra"]["nic_firmware"] = []
        self.manager.verify_nic_firmware(node, None)
        descriptor = self.manager.get_interface_descriptors()[0]
        mock_logger.assert_any_call(
            system_nic._MISSING_MATCHER_RULE.format(
                interface=descriptor.name,
                pci_id=descriptor.pci_id
            )
        )

    @mock.patch.object(SystemNICHardwareManagerMock,
                       'get_interface_descriptors')
    def test_multiple_firmwares(self, mock):
        matchers = 10
        devices_per_matcher = 10
        firmwares = generate_fake_matchers(matchers)
        node = get_dummy_node_info()
        node["extra"]["nic_firmware"] = firmwares
        mappings, _ = generate_fake_devices(devices_per_matcher,
                                            firmwares)
        mock.side_effect = lambda: mappings
        self.assertEqual(
            len(firmwares) * devices_per_matcher,
            len(self.manager.verify_nic_firmware(node, None))
        )

    @mock.patch.object(SystemNICHardwareManagerMock,
                       'get_interface_descriptors')
    def _verify_multiple_firmwares_mismatch(
            self, mismatch, mock, matchers=10, devices_per_matcher=10):
        corruptions = dict(
            map(lambda x: (x, "corrupted-firmware-version-{}".format(x)),
                mismatch))
        firmwares = generate_fake_matchers(matchers)
        node = get_dummy_node_info()
        mappings, good_versions = generate_fake_devices(
            devices_per_matcher, firmwares,
            corruptions=corruptions
        )

        node["extra"]["nic_firmware"] = firmwares
        mock.side_effect = lambda: mappings

        expected_regex = "Found {} firmware version mismatches" \
            .format(len(mismatch))
        self.assertRaisesRegexp(
            errors.CleaningError,
            expected_regex,
            self.manager.verify_nic_firmware,
            node,
            None
        )

    def test_verify_multiple_firmwares_mismatch(self):
        self._verify_multiple_firmwares_mismatch(["eth4", "eth89"])
        self._verify_multiple_firmwares_mismatch(
            ["eth4", "eth89", "eth15", "eth77"])
        self._verify_multiple_firmwares_mismatch(
            ["eth4"])

    @mock.patch.object(SystemNICHardwareManagerMock,
                       'get_interface_descriptors')
    def _verify_nic_firmware_mismatch(self, expected_version, spoof_version,
                                      mock):
        matcher = get_dummy_nic_matcher(version=expected_version)
        node = get_dummy_node_info()
        node["nic_firmware"] = matcher
        pci_id = system_nic._get_pci_id_from_matcher(matcher)
        mock.return_value = [
            system_nic.NICDescriptor(name="enp3s0", pci_id=pci_id,
                                     firmware_version=spoof_version)
        ]
        node = get_dummy_node_info(version=expected_version)
        expected_regex = "(.*\\b{expected}\\b)(.*\\b{actual}\\b).*$" \
            .format(actual=spoof_version, expected=expected_version)
        self.assertRaisesRegexp(
            errors.CleaningError,
            expected_regex,
            self.manager.verify_nic_firmware,
            node,
            None
        )
