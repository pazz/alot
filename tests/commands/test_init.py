# encoding=utf-8

"""Test suite for alot.commands.__init__ module."""

import argparse
import unittest
from unittest import mock

from alot import commands
from alot.commands import thread

# Good descriptive test names often don't fit PEP8, which is meant to cover
# functions meant to be called by humans.
# pylint: disable=invalid-name

# These are tests, don't worry about names like "foo" and "bar"
# pylint: disable=blacklisted-name


class TestLookupCommand(unittest.TestCase):

    def test_look_up_save_attachment_command_in_thread_mode(self):
        cmd, parser, kwargs = commands.lookup_command('save', 'thread')
        # TODO do some more tests with these return values
        self.assertEqual(cmd, thread.SaveAttachmentCommand)
        self.assertIsInstance(parser, argparse.ArgumentParser)
        self.assertDictEqual(kwargs, {})


class TestCommandFactory(unittest.TestCase):

    def test_create_save_attachment_command_with_arguments(self):
        cmd = commands.commandfactory('save --all /foo', mode='thread')
        self.assertIsInstance(cmd, thread.SaveAttachmentCommand)
        self.assertTrue(cmd.all)
        self.assertEqual(cmd.path, u'/foo')


class TestRegisterCommand(unittest.TestCase):
    """Tests for the registerCommand class."""

    def test_registered(self):
        """using registerCommand adds to the COMMANDS dict."""
        with mock.patch('alot.commands.COMMANDS', {'foo': {}}):
            @commands.registerCommand('foo', 'test')
            def foo():  # pylint: disable=unused-variable
                pass

            self.assertIn('test', commands.COMMANDS['foo'])
