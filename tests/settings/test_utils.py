# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Tests for the alot.setting.utils module."""

import unittest
from unittest import mock

from alot.settings import utils


class TestResolveAtt(unittest.TestCase):

    __patchers = []
    fallback = mock.Mock()
    fallback.foreground = 'some fallback foreground value'
    fallback.background = 'some fallback background value'

    @classmethod
    def setUpClass(cls):
        cls.__patchers.append(mock.patch(
            'alot.settings.utils.AttrSpec',
            mock.Mock(side_effect=lambda *args: args)))
        for p in cls.__patchers:
            p.start()

    @classmethod
    def tearDownClass(cls):
        for p in cls.__patchers:
            p.stop()

    @staticmethod
    def _mock(foreground, background):
        """Create a mock object that is needed very often."""
        m = mock.Mock()
        m.foreground = foreground
        m.background = background
        return m

    def test_passing_none_returns_fallback(self):
        actual = utils.resolve_att(None, self.fallback)
        self.assertEqual(actual, self.fallback)

    def test_empty_string_in_background_picks_up_background_from_fallback(self):
        attr = self._mock('valid foreground', '')
        expected = (attr.foreground, self.fallback.background)
        actual = utils.resolve_att(attr, self.fallback)
        self.assertTupleEqual(actual, expected)

    def test_default_in_background_picks_up_background_from_fallback(self):
        attr = self._mock('valid foreground', 'default')
        expected = attr.foreground, self.fallback.background
        actual = utils.resolve_att(attr, self.fallback)
        self.assertTupleEqual(actual, expected)

    def test_empty_string_in_foreground_picks_up_foreground_from_fallback(self):
        attr = self._mock('', 'valid background')
        expected = self.fallback.foreground, attr.background
        actual = utils.resolve_att(attr, self.fallback)
        self.assertTupleEqual(actual, expected)

    def test_default_in_foreground_picks_up_foreground_from_fallback(self):
        attr = self._mock('default', 'valid background')
        expected = self.fallback.foreground, attr.background
        actual = utils.resolve_att(attr, self.fallback)
        self.assertTupleEqual(actual, expected)

    def test_other_values_are_used(self):
        attr = self._mock('valid foreground', 'valid background')
        expected = attr.foreground, attr.background
        actual = utils.resolve_att(attr, self.fallback)
        self.assertTupleEqual(actual, expected)
