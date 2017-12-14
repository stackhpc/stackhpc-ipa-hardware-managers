# Copyright (c) 2017 StackHPC Ltd.
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

import unittest

from ironic_python_agent import errors
from ironic_python_agent import hardware

import mock

from stackhpc_ipa_hardware_managers import system_bios

_DUMMY_NODE_INFO = {
    'extra': {
        'system_vendor': {
            'product_name': 'PowerEdge R630',
            'manufacturer': 'Dell Inc.',
            'bios_version': '2.3.4'
        }
    }
}


class TestSystemBiosManager(unittest.TestCase):

    def setUp(self):
        self.manager = system_bios.SystemBiosHardwareManager()
        self.node = dict(_DUMMY_NODE_INFO)

    def test_evaluate_hardware_support(self):
        actual = self.manager.evaluate_hardware_support()
        self.assertEqual(hardware.HardwareSupport.SERVICE_PROVIDER, actual)

    @mock.patch('ironic_python_agent.utils.execute', autospec=True)
    def test_verify_bios_version_ok(self, mock_execute):
        mock_execute.side_effect = [('PowerEdge R630\n', None),
                                    ('2.3.4\n', None)]
        self.assertTrue(self.manager.verify_bios_version(self.node, None))

    @mock.patch('ironic_python_agent.utils.execute', autospec=True)
    def test_verify_bios_version_bios_mismatch(self, mock_execute):
        mock_execute.side_effect = [('PowerEdge R630\n', None),
                                    ('1.0\n', None)]
        self.assertRaisesRegexp(errors.CleaningError,
                                "^(?=.*\\b2.3.4\\b)(?=.*\\b1.0\\b).*$",
                                self.manager.verify_bios_version,
                                self.node,
                                None)

    @mock.patch('ironic_python_agent.utils.execute', autospec=True)
    def test_verify_bios_version_product_mismatch(self, mock_execute):
        mock_execute.side_effect = [('T4000\n', None),
                                    ('2.3.4\n', None)]
        self.assertRaisesRegexp(
            errors.CleaningError,
            "^(?=.*\\bPowerEdge R630\\b)(?=.*\\bT4000\\b).*$",
            self.manager.verify_bios_version,
            self.node,
            None)

    @mock.patch('ironic_python_agent.utils.execute', autospec=True)
    def test_verify_bios_version_missing_product_name(self, mock_execute):
        mock_execute.side_effect = [('PowerEdge R640\n', None),
                                    ('2.3.4\n', None)]
        self.node['extra']['system_vendor'].pop('product_name')
        self.assertRaisesRegexp(errors.CleaningError,
                                'product_name',
                                self.manager.verify_bios_version,
                                self.node,
                                None)

    @mock.patch('ironic_python_agent.utils.execute', autospec=True)
    def test_verify_bios_version_missing_bios_version(self, mock_execute):
        mock_execute.side_effect = [('PowerEdge R640\n', None),
                                    ('2.3.4\n', None)]
        self.node['extra']['system_vendor'].pop('bios_version')
        self.assertRaisesRegexp(errors.CleaningError,
                                'bios_version',
                                self.manager.verify_bios_version,
                                self.node,
                                None)
