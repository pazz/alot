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

    shell_parent = False  # run alot from a shell, as in a terminal emulator

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
            editor_cmd = true
            # an expiring notification redraws the screen, which can happen
            # just after command() has sent ':' and pass for the prompt
            notify_timeout = 3600
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
                argv = [sys.executable, '-m', 'alot',
                        '-n', self.notmuch_config, '-c', self.alot_config,
                        'search', 'tag:inbox']
                if self.shell_parent:
                    argv = ['/bin/sh', '-c', '"$@"; true', 'sh'] + argv
                os.execve(argv[0], argv, env)
            finally:
                os._exit(127)  # never return into the test runner
        self.addCleanup(self._kill)
        self.wait_for('%d of %d' % (self.thread_count, self.thread_count))

    def _kill(self):
        if self.pid is not None:
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)
        if self.fd is not None:
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
        self.settle()
        os.kill(self.pid, signal.SIGSTOP)
        _, status = os.waitpid(self.pid, os.WUNTRACED)
        self.assertTrue(os.WIFSTOPPED(status))
        self.output = b''
        os.kill(self.pid, signal.SIGCONT)
        self.wait_for('%d of %d' % (self.thread_count, self.thread_count))
        self.assertResponsive()

    def test_tag_in_thread_mode_is_shown(self):
        self.send('\r')  # open the first thread
        self.wait_for('thread]')
        while self._read(0.5):  # let the thread view settle
            pass
        self.output = b''
        self.command('tag e2e-tag')
        self.wait_for('e2e-tag')

    def test_thread_mode_tags_shown_back_in_search(self):
        self.send('\r')  # open the first thread
        self.wait_for('thread]')
        self.command('tag e2e-back')
        self.wait_for('e2e-back')
        self.command('bclose')
        self.wait_for('search] for "tag:inbox"')
        self.settle()
        # the threadline in the search buffer shows the new tag
        self.assertRegex(self.screen_text(),
                         r'\(1\) +[\w -]*e2e-back[\w -]* foo@bar\.com test')

    def test_back_to_search_with_malformed_query(self):
        self.command('refine date:foo..bar')
        self.wait_for('malformed query string')
        self.command('taglist')
        self.wait_for('taglist]')
        self.command('bclose')
        self.wait_for('search] for "date:foo..bar"')
        self.settle()
        # returning must not query the index with the malformed query
        self.assertNotIn('Xapian exception', self.screen_text())

    def test_external_command(self):
        self.command('shellescape --thread=False true')
        self.assertResponsive()


class TestModes(EndToEndTestCase):

    def test_thread(self):
        self.command('search subject:"test subject"')
        self.wait_for('search] for "subject:"test subject""')
        self.settle()
        self.send('\r')
        self.wait_for(': thread] test subject')
        self.wait_for('test body')

    def test_bufferlist(self):
        self.command('bufferlist')
        self.wait_for(': bufferlist]')

    def test_taglist(self):
        self.command('taglist')
        self.wait_for(': taglist]')
        self.wait_for('inbox')

    def test_namedqueries(self):
        self.command('savequery e2e-query tag:inbox')
        self.command('namedqueries')
        self.wait_for(': namedqueries]')
        self.wait_for('e2e-query')

    def test_envelope(self):
        self.command('compose --to=to@example.com --subject=e2e-subject')
        self.wait_for(': envelope (plaintext)]')
        self.wait_for('Test User <test@example.com>')  # From, set by alot



class TestEmptyMessageFile(EndToEndTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cur = os.path.join(cls.dir, 'mail', 'cur')
        for mid, extra in (('parent', ''),
                           ('reply', 'In-Reply-To: <parent@e2e>')):
            cls._write(os.path.join(cur, mid + ':2,S'), '''\
                From: a@example.com
                Subject: e2e-empty
                Message-ID: <{mid}@e2e>
                {extra}

                {mid} body
                ''', mid=mid, extra=extra)
        subprocess.run(['notmuch', 'new', '--quiet', '--no-hooks'],
                       env=cls.env, check=True)
        cls.thread_count += 2
        # the file vanishes into nothing after indexing
        open(os.path.join(cur, 'parent:2,S'), 'w').close()

    def test_open_and_move(self):
        self.command('search subject:e2e-empty')
        self.wait_for('search] for "subject:e2e-empty"')
        self.settle()
        self.send('\r')
        self.wait_for('reply body')
        for move in ('move up', 'move down', 'move first', 'move last'):
            self.command(move)
        self.assertResponsive()


class TestClosedTerminal(EndToEndTestCase):

    def test_closed_terminal(self):
        self.command('search NOT tag:inbox')
        self.wait_for('search] for "NOT tag:inbox"')
        os.close(self.fd)  # the terminal emulator goes away: SIGHUP
        self.fd = None
        # wait for alot itself: with a shell parent, self.pid is the shell
        deadline = time.monotonic() + TIMEOUT
        while not os.path.exists(self.marker):
            if time.monotonic() > deadline:
                self.fail('exit hook did not run')
            time.sleep(0.1)
        history = os.path.join(self.dir, '.cache', 'alot', 'history',
                               'commands')
        with open(history) as f:
            self.assertIn('search NOT tag:inbox', f.read())


class TestClosedTerminalWithShell(TestClosedTerminal):
    """the shell, not alot, leads the session and gets SIGHUP first"""

    shell_parent = True
