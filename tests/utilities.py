# encoding=utf-8
# Copyright © 2017 Dylan Baker
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Helpers for unittests themselves."""

import asyncio
import functools
import unittest
from unittest import mock

import gpg


def _tear_down_class_wrapper(original, cls):
    """Ensure that doClassCleanups is called after tearDownClass."""
    try:
        original()
    finally:
        cls.doClassCleanups()


def _set_up_class_wrapper(original, cls):
    """If setUpClass fails, call doClassCleanups."""
    try:
        original()
    except Exception:
        cls.doClassCleanups()
        raise


class TestCaseClassCleanup(unittest.TestCase):

    """A subclass of unittest.TestCase which adds classlevel clenups methods.
    """

    __stack = []

    def __new__(cls, _):
        """Wrap the tearDownClass method to esnure that doClassCleanups gets
        called.

        Because doCleanups (the test instance level version of this
        functionality) is called in code we can't supclass we need to do some
        hacking to ensure it's called. that hackery is in the form of wrapping
        the call to tearDownClass and setupClass methods.
        """
        original = cls.tearDownClass

        # Get a unique object, otherwise functools.update_wrapper will always
        # act on the same object. We're using functools.partial as a proxy to
        # receive that information.
        #
        # We're also passing the original implementation to the wrapper
        # function as an argument, because it is being passed an unbound class
        # method the calling function will need to pass cls to it as an
        # argument.
        unique = functools.partial(_tear_down_class_wrapper, original, cls)

        # the classmethod decorator hides the __module__ attribute, so don't
        # try to set it. In python 3.x this is no longer true and the lat
        # parameter of this call can be removed
        functools.update_wrapper(unique, original, ['__name__', '__doc__'])

        # Repalce the orinal tearDownClass method with our wrapper
        cls.tearDownClass = unique

        # Do essentially the same thing for setup, but to ensure that
        # doClassCleanups is only called if there is an exception in the
        # setUpClass method.
        original = cls.setUpClass
        unique = functools.partial(_set_up_class_wrapper, original, cls)
        functools.update_wrapper(unique, original, ['__name__', '__doc__'])
        cls.setUpClass = unique

        return unittest.TestCase.__new__(cls)

    @classmethod
    def addClassCleanup(cls, function, *args, **kwargs):  # pylint: disable=invalid-name
        cls.__stack.append((function, args, kwargs))

    @classmethod
    def doClassCleanups(cls):  # pylint: disable=invalid-name
        while cls.__stack:
            func, args, kwargs = cls.__stack.pop()

            # TODO: Should exceptions be ignored from this?
            # TODO: addCleanups success if part of the success of the test,
            # what should we do here?
            func(*args, **kwargs)


class ModuleCleanup(object):
    """Class for managing module level setup and teardown fixtures.

    Because of the way unittest is implemented it's rather difficult to write
    elegent fixtures because setUpModule and tearDownModule must exist when the
    module is initialized, so you can't do things like assign the methods to
    setUpModule and tearDownModule, nor can you just do some globals
    manipulation.
    """

    def __init__(self):
        self.__stack = []

    def do_cleanups(self):
        while self.__stack:
            func, args, kwargs = self.__stack.pop()
            func(*args, **kwargs)

    def add_cleanup(self, func, *args, **kwargs):
        self.__stack.append((func, args, kwargs))

    def wrap_teardown(self, teardown):

        @functools.wraps(teardown)
        def wrapper():
            try:
                teardown()
            finally:
                self.do_cleanups()

        return wrapper

    def wrap_setup(self, setup):

        @functools.wraps(setup)
        def wrapper():
            try:
                setup()
            except Exception:
                self.do_cleanups()
                raise

        return wrapper


def make_uid(email, uid=u'mocked', revoked=False, invalid=False,
             validity=gpg.constants.validity.FULL):
    uid_ = mock.Mock()
    uid_.email = email
    uid_.uid = uid
    uid_.revoked = revoked
    uid_.invalid = invalid
    uid_.validity = validity

    return uid_


def make_key(revoked=False, expired=False, invalid=False, can_encrypt=True,
             can_sign=True):
    mock_key = mock.Mock()
    mock_key.uids = [make_uid(u'foo@example.com')]
    mock_key.revoked = revoked
    mock_key.expired = expired
    mock_key.invalid = invalid
    mock_key.can_encrypt = can_encrypt
    mock_key.can_sign = can_sign

    return mock_key


def make_ui(**kwargs):
    ui = mock.Mock(**kwargs)
    ui.paused.return_value = mock.MagicMock()

    return ui


def async_test(coro):
    """Run an asyncrounous test synchronously."""

    @functools.wraps(coro)
    def _actual(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))

    return _actual
