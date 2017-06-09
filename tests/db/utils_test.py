# encoding: utf-8
# Copyright (C) 2017 Lucas Hoffmann
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import email
import unittest

from alot.db import utils


class TestGetParams(unittest.TestCase):

    mailstring = '\n'.join([
        'From: me',
        'To: you',
        'Subject: header field capitalisation',
        'Content-type: text/plain; charset=utf-8',
        'X-Header: param=one; and=two; or=three',
        "X-Quoted: param=utf-8''%C3%9Cmlaut; second=plain%C3%9C",
        'X-UPPERCASE: PARAM1=ONE; PARAM2=TWO'
        '\n',
        'content'
        ])
    mail = email.message_from_string(mailstring)

    def test_returns_content_type_parameters_by_default(self):
        actual = utils.get_params(self.mail)
        expected = {'text/plain': '', 'charset': 'utf-8'}
        self.assertDictEqual(actual, expected)

    def test_can_return_params_of_any_header_field(self):
        actual = utils.get_params(self.mail, header='x-header')
        expected = {'param': 'one', 'and': 'two', 'or': 'three'}
        self.assertDictEqual(actual, expected)

    @unittest.expectedFailure
    def test_parameters_are_decoded(self):
        actual = utils.get_params(self.mail, header='x-quoted')
        expected = {'param': 'Ümlaut', 'second': 'plain%C3%9C'}
        self.assertDictEqual(actual, expected)

    def test_parameters_names_are_converted_to_lowercase(self):
        actual = utils.get_params(self.mail, header='x-uppercase')
        expected = {'param1': 'ONE', 'param2': 'TWO'}
        self.assertDictEqual(actual, expected)

    def test_returns_empty_dict_if_header_not_present(self):
        actual = utils.get_params(self.mail, header='x-header-not-present')
        self.assertDictEqual(actual, dict())

    def test_returns_failobj_if_header_not_present(self):
        failobj = [('my special failobj for the test', 'needs to be a pair!')]
        actual = utils.get_params(self.mail, header='x-header-not-present',
                                  failobj=failobj)
        expected = dict(failobj)
        self.assertEqual(actual, expected)

