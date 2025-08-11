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

"""
test_example_hardware_manager
----------------------------------

Tests for `example_hardware_manager` module.
"""

from ironic_python_agent import errors

from example_hardware_manager.manager import ExampleHardwareManager
from example_hardware_manager.tests import base


import mock


class TestExample_hardware_manager(base.TestCase):

    def setUp(self):
        super(TestExample_hardware_manager, self).setUp()
        self.manager = ExampleHardwareManager()

    @mock.patch('ironic_python_agent.hardware.dispatch_to_managers',
                autospec=True)
    def test_example_clean_step(self, _mock_dispatch):
        node = {"extra": {"example_clean_step_msg": "hello"}}
        self.assertRaises(errors.CleaningError,
                          self.manager.example_step,
                          node,
                          None)
