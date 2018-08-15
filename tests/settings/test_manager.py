# Copyright (C) 2017  Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Test suite for alot.settings.manager module."""

import os
import re
import tempfile
import textwrap
import unittest
from unittest import mock

from alot.settings.manager import SettingsManager
from alot.settings.errors import ConfigError, NoMatchingAccount

from .. import utilities


class TestSettingsManager(unittest.TestCase):

    def test_reading_synchronize_flags_from_notmuch_config(self):
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = true
                """))
        self.addCleanup(os.unlink, f.name)

        manager = SettingsManager()
        manager.read_notmuch_config(f.name)
        actual = manager.get_notmuch_setting('maildir', 'synchronize_flags')
        self.assertTrue(actual)

    def test_parsing_notmuch_config_with_non_bool_synchronize_flag_fails(self):
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = not bool
                """))
        self.addCleanup(os.unlink, f.name)

        with self.assertRaises(ConfigError):
            manager = SettingsManager()
            manager.read_notmuch_config(f.name)

    def test_reload_notmuch_config(self):
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = false
                """))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager()
        manager.read_notmuch_config(f.name)

        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = true
                """))
        self.addCleanup(os.unlink, f.name)

        manager.read_notmuch_config(f.name)
        actual = manager.get_notmuch_setting('maildir', 'synchronize_flags')
        self.assertTrue(actual)

    def test_read_config_doesnt_exist(self):
        """If there is not an alot config things don't break.

        This specifically tests for issue #1094, which is caused by the
        defaults not being loaded if there isn't an alot config files, and thus
        calls like `get_theming_attribute` fail with strange exceptions.
        """
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [maildir]
                synchronize_flags = true
                """))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager()
        manager.read_config(f.name)

        manager.get_theming_attribute('global', 'body')

    def test_unknown_settings_in_config_are_logged(self):
        # todo: For py3, don't mock the logger, use assertLogs
        unknown_settings = ['templates_dir', 'unknown_section', 'unknown_1',
                            'unknown_2']
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                {x[0]} = /templates/dir
                [{x[1]}]
                    # Values in unknown sections are not reported.
                    barfoo = barfoo
                [tags]
                    [[foobar]]
                        {x[2]} = baz
                        translated = translation
                        {x[3]} = bar
                """.format(x=unknown_settings)))
        self.addCleanup(os.unlink, f.name)

        with mock.patch('alot.settings.utils.logging') as mock_logger:
            manager = SettingsManager()
            manager.read_config(f.name)

        success = any(all([s in call_args[0][0] for s in unknown_settings])
                      for call_args in mock_logger.info.call_args_list)
        self.assertTrue(success, msg='Could not find all unknown settings in '
                        'logging.info.\nUnknown settings:\n{}\nCalls to mocked'
                        ' logging.info:\n{}'.format(
                            unknown_settings, mock_logger.info.call_args_list))

    def test_read_notmuch_config_doesnt_exist(self):
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [accounts]
                    [[default]]
                        realname = That Guy
                        address = thatguy@example.com
                """))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager()
        manager.read_notmuch_config(f.name)

        setting = manager.get_notmuch_setting('foo', 'bar')
        self.assertIsNone(setting)

    def test_choke_on_invalid_regex_in_tagstring(self):
        tag = 'to**do'
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [tags]
                    [[{tag}]]
                        normal = '','', 'white','light red', 'white','#d66'
                """.format(tag=tag)))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager()
        manager.read_config(f.name)
        with self.assertRaises(re.error):
            manager.get_tagstring_representation(tag)

    def test_translate_tagstring_prefix(self):
        # Test for behavior mentioned in bcb2670f56fa251c0f1624822928d664f6455902,
        # namely that 'foo' does not match 'foobar'
        tag = 'foobar'
        tagprefix = 'foo'
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [tags]
                    [[{tag}]]
                        translated = matched
                """.format(tag=tagprefix)))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager()
        manager.read_config(f.name)
        tagrep = manager.get_tagstring_representation(tag)
        self.assertIs(tagrep['translated'], tag)
        tagprefixrep = manager.get_tagstring_representation(tagprefix)
        self.assertEqual(tagprefixrep['translated'], 'matched')

    def test_translate_tagstring_prefix_regex(self):
        # Test for behavior mentioned in bcb2670f56fa251c0f1624822928d664f6455902,
        # namely that 'foo.*' does match 'foobar'
        tagprefixregexp = 'foo.*'
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [tags]
                    [[{tag}]]
                        translated = matched
                """.format(tag=tagprefixregexp)))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager()
        manager.read_config(f.name)
        def matched(t):
            return manager.get_tagstring_representation(t)['translated'] == 'matched'
        self.assertTrue(all(matched(t) for t in ['foo', 'foobar', tagprefixregexp]))
        self.assertFalse(any(matched(t) for t in ['bar', 'barfoobar']))

    def test_translate_regexp(self):
        # Test for behavior mentioned in 108df3df8571aea2164a5d3fc42655ac2bd06c17
        # namely that translations themselves can use regex
        tag = "notmuch::foo"
        section = "[[notmuch::.*]]"
        translation = r"'notmuch::(.*)', 'nm:\1'"
        translated_goal = "nm:foo"

        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(textwrap.dedent("""\
                [tags]
                    {section}
                        translation = {translation}
                """.format(section=section, translation=translation)))
        self.addCleanup(os.unlink, f.name)
        manager = SettingsManager()
        manager.read_config(f.name)
        self.assertEqual(manager.get_tagstring_representation(tag)['translated'], translated_goal)

class TestSettingsManagerExpandEnvironment(unittest.TestCase):
    """ Tests SettingsManager._expand_config_values """
    setting_name = 'template_dir'
    xdg_name = 'XDG_CONFIG_HOME'
    default = '$%s/alot/templates' % xdg_name
    xdg_fallback = '~/.config'
    xdg_custom = '/foo/bar/.config'
    default_expanded = default.replace('$%s' % xdg_name, xdg_fallback)

    def test_user_setting_and_env_not_empty(self):
        user_setting = '/path/to/template/dir'

        with mock.patch.dict('os.environ', {self.xdg_name: self.xdg_custom}):
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
                f.write('template_dir = {}'.format(user_setting))
            self.addCleanup(os.unlink, f.name)

            manager = SettingsManager()
            manager.read_config(f.name)
            self.assertEqual(manager._config.get(self.setting_name),
                             os.path.expanduser(user_setting))

    def test_configobj_and_env_expansion(self):
        """ Three expansion styles:
            %(FOO)s - expanded by ConfigObj (string interpolation)
            $FOO and ${FOO} - should be expanded with environment variable
        """
        foo_env = 'foo_set_from_env'
        with mock.patch.dict('os.environ', {self.xdg_name: self.xdg_custom,
                                            'foo': foo_env}):
            foo_in_config = 'foo_set_in_config'
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
                f.write(textwrap.dedent("""\
                foo = {}
                template_dir = ${{XDG_CONFIG_HOME}}/$foo/%(foo)s/${{foo}}
                """.format(foo_in_config)))
            self.addCleanup(os.unlink, f.name)

            manager = SettingsManager()
            manager.read_config(f.name)
            self.assertEqual(manager._config.get(self.setting_name),
                             os.path.join(self.xdg_custom, foo_env,
                                          foo_in_config, foo_env))



class TestSettingsManagerGetAccountByAddress(utilities.TestCaseClassCleanup):
    """Test the account_matching_address helper."""

    @classmethod
    def setUpClass(cls):
        config = textwrap.dedent("""\
            [accounts]
                [[default]]
                    realname = That Guy
                    address = that_guy@example.com
                    sendmail_command = /bin/true

                [[other]]
                    realname = A Dude
                    address = a_dude@example.com
                    sendmail_command = /bin/true
            """)

        # Allow settings.reload to work by not deleting the file until the end
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
            f.write(config)
        cls.addClassCleanup(os.unlink, f.name)

        # Replace the actual settings object with our own using mock, but
        # ensure it's put back afterwards
        cls.manager = SettingsManager()
        cls.manager.read_config(f.name)

    def test_exists_addr(self):
        acc = self.manager.account_matching_address(u'that_guy@example.com')
        self.assertEqual(acc.realname, 'That Guy')

    def test_doesnt_exist_return_default(self):
        acc = self.manager.account_matching_address(u'doesntexist@example.com',
                                                    return_default=True)
        self.assertEqual(acc.realname, 'That Guy')

    def test_doesnt_exist_raise(self):
        with self.assertRaises(NoMatchingAccount):
            self.manager.account_matching_address(u'doesntexist@example.com')

    def test_doesnt_exist_no_default(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write(b'')
            settings = SettingsManager()
            settings.read_config(f.name)
        with self.assertRaises(NoMatchingAccount):
            settings.account_matching_address('that_guy@example.com',
                                              return_default=True)

    def test_real_name_will_be_stripped_before_matching(self):
        acc = self.manager.account_matching_address(
            'That Guy <a_dude@example.com>')
        self.assertEqual(acc.realname, 'A Dude')

    def test_address_case(self):
        """Some servers do not differentiate addresses by case.

        So, for example, "foo@example.com" and "Foo@example.com" would be
        considered the same. Among servers that do this gmail, yahoo, fastmail,
        anything running Exchange (i.e., most large corporations), and others.
        """
        acc1 = self.manager.account_matching_address('That_guy@example.com')
        acc2 = self.manager.account_matching_address('that_guy@example.com')
        self.assertIs(acc1, acc2)
