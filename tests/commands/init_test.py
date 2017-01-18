# encoding=utf-8

"""Test suite for alot.commands.__init__ module."""

import argparse
import unittest

from alot import commands
from alot.commands import thread


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
