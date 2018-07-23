# Copyright © 2018 Dylan Baker
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

import multiprocessing
import unittest

from alot.db import manager


class TestSizedPipe(unittest.TestCase):

    def test_basic(self):
        send_p, recv_p = multiprocessing.Pipe()
        sem = multiprocessing.Semaphore()
        pipe = manager.SizedPipe(send_p, None, sem)

        sentinel = 42

        pipe.send(sentinel)
        val = recv_p.recv()

        assert val == sentinel

    def test_non_writable(self):
        send_p, _ = multiprocessing.Pipe()
        sem = multiprocessing.Semaphore()
        pipe = manager.SizedPipe(send_p, None, sem)

        with self.assertRaises(OSError):
            pipe.recv()

    def test_non_readable(self):
        send_p, _ = multiprocessing.Pipe()
        sem = multiprocessing.Semaphore()
        pipe = manager.SizedPipe(send_p, sem, None)

        with self.assertRaises(OSError):
            pipe.send(12)


class TestSizedPipeFunc(unittest.TestCase):

    def test_duplex(self):
        read, write = manager.sized_pipe()
        write.send(12)
        assert read.recv() == 12

        read.send("foo")
        assert write.recv() == "foo"

    def test_unidirectional(self):
        read, write = manager.sized_pipe(duplex=False)
        write.send(12)
        assert read.recv() == 12

        with self.assertRaises(OSError):
            read.send("foo")

    def test_maxsize_too_small(self):
        with self.assertRaises(ValueError):
            manager.sized_pipe(maxsize=-1)

