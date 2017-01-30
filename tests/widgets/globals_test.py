# encoding=utf-8
# Copyright © 2017 Dylan Baker

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for the alot.widgets.globals module."""

from __future__ import absolute_import

import unittest

import mock

from alot.widgets import globals as globals_


class TestTagWidget(unittest.TestCase):

    def test_sort(self):
        """Test sorting."""
        with mock.patch(
                'alot.widgets.globals.settings.get_tagstring_representation',
                lambda t, _, __: {'translated': t, 'normal': None,
                                  'focussed': None}):
            expected = ['a', 'z', 'aa', 'bar', 'foo']
            actual = [g.translated for g in
                      sorted(globals_.TagWidget(x) for x in expected)]
            self.assertListEqual(actual, expected)
