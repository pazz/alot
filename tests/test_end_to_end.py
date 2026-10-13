# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""Run alot in a pseudo terminal against a small notmuch database."""

import fcntl
import glob
import os
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import textwrap
import time
import unittest

import alot

TIMEOUT = 10
ESCAPES = re.compile(rb'\x1b(\[[0-?]*[ -/]*[@-~]|[()][0-9A-B]|[=>78])')
MAILS = os.path.join(os.path.dirname(__file__), 'static', 'mail')


@unittest.skipUnless(shutil.which('notmuch'), 'needs the notmuch command')
class EndToEndTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.addClassCleanup(shutil.rmtree, cls.dir)
        maildir = os.path.join(cls.dir, 'mail')
        for sub in ('cur', 'new', 'tmp'):
            os.makedirs(os.path.join(maildir, sub))
        mails = sorted(glob.glob(os.path.join(MAILS, '*.eml')))
        for i, mail in enumerate(mails):
            shutil.copy(mail, os.path.join(maildir, 'cur', '%d:2,S' % i))
        cls.thread_count = len(mails)
        cls.notmuch_config = cls._write('notmuch-config', '''\
            [database]
            path={maildir}
            [user]
            name=Test User
            primary_email=test@example.com
            [new]
            tags=inbox
            [maildir]
            synchronize_flags=false
            ''', maildir=maildir)
        cls.marker = os.path.join(cls.dir, 'exit-hook-ran')
        hooks = cls._write('hooks.py', '''\
            def exit():
                open({marker!r}, 'w').close()
            ''', marker=cls.marker)
        cls.alot_config = cls._write('alot-config', '''\
            hooksfile = {hooks}
            [accounts]
                [[test]]
                    realname = Test User
                    address = test@example.com
            ''', hooks=hooks)
        # keep the developer's notmuch and alot setup out of the tests
        cls.env = {k: v for k, v in os.environ.items()
                   if not k.startswith(('NOTMUCH_', 'XDG_'))}
        cls.env.update(HOME=cls.dir, NOTMUCH_CONFIG=cls.notmuch_config)
        subprocess.run(['notmuch', 'new', '--quiet', '--no-hooks'],
                       env=cls.env, check=True)

    @classmethod
    def _write(cls, name, template, **values):
        path = os.path.join(cls.dir, name)
        with open(path, 'w') as f:
            f.write(textwrap.dedent(template).format(**values))
        return path

    def setUp(self):
        if os.path.exists(self.marker):
            os.unlink(self.marker)
        self.output = b''
        self.pid, self.fd = pty.fork()
        if self.pid == 0:  # child: run alot in an 80x24 terminal
            try:
                fcntl.ioctl(0, termios.TIOCSWINSZ,
                            struct.pack('HHHH', 24, 80, 0, 0))
                # the modules this test process sees (HOME has changed, so
                # user site-packages would be lost otherwise), alot first
                path = [os.path.dirname(os.path.dirname(alot.__file__))]
                env = dict(self.env, TERM='xterm', PYTHONPATH=os.pathsep.join(
                    path + [p for p in sys.path if p]))
                os.execve(sys.executable,
                          [sys.executable, '-m', 'alot',
                           '-n', self.notmuch_config, '-c', self.alot_config,
                           'search', 'tag:inbox'], env)
            finally:
                os._exit(127)  # never return into the test runner
        self.addCleanup(self._kill)
        self.wait_for('%d of %d' % (self.thread_count, self.thread_count))

    def _kill(self):
        if self.pid is not None:
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)
        os.close(self.fd)

    def _read(self, timeout):
        """Read what alot wrote within `timeout` seconds."""
        if select.select([self.fd], [], [], timeout)[0]:
            try:
                data = os.read(self.fd, 65536)
            except OSError:  # alot has exited
                return False
            self.output += data
            return bool(data)
        return False

    def screen_text(self):
        return ESCAPES.sub(b'', self.output).decode('utf-8', 'replace')

    def wait_for(self, text):
        """Wait for `text` on screen, or for raw `bytes` in the output."""
        def seen():
            if isinstance(text, bytes):
                return text in self.output
            return text in self.screen_text()
        deadline = time.monotonic() + TIMEOUT
        while not seen():
            if time.monotonic() > deadline:
                self.fail('%r did not appear in %r'
                          % (text, self.screen_text()))
            self._read(0.1)

    def send(self, keys):
        os.write(self.fd, keys.encode())

    def settle(self):
        """Wait until alot has stopped drawing."""
        deadline = time.monotonic() + TIMEOUT
        while self._read(0.3) and time.monotonic() < deadline:
            pass

    def command(self, cmdline):
        # a ':' drawn earlier, e.g. in 'tag:inbox', must not pass for the
        # prompt, which opens asynchronously
        self.settle()
        self.output = b''
        self.send(':')
        self.wait_for(':')
        self.send(cmdline + '\r')

    def wait_for_exit(self):
        """Return alot's exit status."""
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            self._read(0.1)
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.pid = None
                return os.waitstatus_to_exitcode(status)
        self.fail('alot did not exit')

    def assertTerminalRestored(self):
        lflag = termios.tcgetattr(self.fd)[3]
        self.assertTrue(lflag & termios.ICANON, 'terminal left in raw mode')
        self.assertTrue(lflag & termios.ECHO, 'terminal left without echo')

    def assertResponsive(self):
        self.output = b''
        self.command('search NOT tag:inbox')
        self.wait_for('search] for "NOT tag:inbox"')


class TestStartAndExit(EndToEndTestCase):

    def test_quit(self):
        self.send('q')
        self.assertEqual(self.wait_for_exit(), 0)
        self.assertTerminalRestored()
        self.assertTrue(os.path.exists(self.marker), 'exit hook did not run')

    def test_sigterm(self):
        os.kill(self.pid, signal.SIGTERM)
        self.assertEqual(self.wait_for_exit(), 0)
        self.assertTerminalRestored()
        self.assertTrue(os.path.exists(self.marker), 'exit hook did not run')

    def test_sigint(self):
        os.kill(self.pid, signal.SIGINT)
        self.assertEqual(self.wait_for_exit(), 0)
        self.assertTerminalRestored()
        self.assertTrue(os.path.exists(self.marker), 'exit hook did not run')


class TestRunning(EndToEndTestCase):

    @unittest.skipUnless(os.path.exists('/proc/self/status'), 'needs /proc')
    def test_idle_without_wakeups(self):
        def switches():
            with open('/proc/%d/status' % self.pid) as f:
                return sum(int(line.split()[1]) for line in f
                           if 'ctxt_switches' in line)
        self.settle()
        before = switches()
        time.sleep(2)
        # an idle event loop that polls wakes up dozens of times a second
        self.assertLess(switches() - before, 10)

    def test_sigusr1_keeps_running(self):
        os.kill(self.pid, signal.SIGUSR1)
        self.assertResponsive()

    def test_resize(self):
        self.output = b''
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ,
                    struct.pack('HHHH', 30, 100, 0, 0))
        self.wait_for(b'\x1b[30;')  # a redraw in the new last line
        self.assertResponsive()

    def test_stop_and_continue(self):
        # ctrl-z cannot be tested here: alot leads its own session, so the
        # kernel discards SIGTSTP; SIGSTOP stops it all the same
        os.kill(self.pid, signal.SIGSTOP)
        _, status = os.waitpid(self.pid, os.WUNTRACED)
        self.assertTrue(os.WIFSTOPPED(status))
        os.kill(self.pid, signal.SIGCONT)
        self.assertResponsive()

    def test_external_command(self):
        self.command('shellescape --thread=False true')
        self.assertResponsive()
