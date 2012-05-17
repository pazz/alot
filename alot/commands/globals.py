import os
import code
from twisted.internet import threads
import subprocess
import shlex
import email
import urwid
from twisted.internet.defer import inlineCallbacks
import logging
import argparse
import glob

from alot.commands import Command, registerCommand
from alot.completion import CommandLineCompleter
from alot.commands import CommandParseError
from alot.commands import commandfactory
from alot import buffers
from alot import widgets
from alot import helper
from alot import crypto
from alot.db.errors import DatabaseLockedError
from alot.completion import ContactsCompleter
from alot.completion import AccountCompleter
from alot.db.envelope import Envelope
from alot import commands
from alot.settings import settings
from alot.errors import GPGProblem

MODE = 'global'


@registerCommand(MODE, 'exit')
class ExitCommand(Command):
    """shut down cleanly"""
    @inlineCallbacks
    def apply(self, ui):
        if settings.get('bug_on_exit'):
            if (yield ui.choice('realy quit?', select='yes', cancel='no',
                               msg_position='left')) == 'no':
                return
        for b in ui.buffers:
            b.cleanup()
        ui.exit()


@registerCommand(MODE, 'search', usage='search query', arguments=[
    (['--sort'], {'help':'sort order', 'choices':[
                   'oldest_first', 'newest_first', 'message_id', 'unsorted']}),
    (['query'], {'nargs':argparse.REMAINDER, 'help':'search string'})])
class SearchCommand(Command):
    """open a new search buffer"""
    def __init__(self, query, sort=None, **kwargs):
        """
        :param query: notmuch querystring
        :type query: str
        """
        self.query = ' '.join(query)
        self.order = sort
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.query:
            open_searches = ui.get_buffers_of_type(buffers.SearchBuffer)
            to_be_focused = None
            for sb in open_searches:
                if sb.querystring == self.query:
                    to_be_focused = sb
            if to_be_focused:
                if ui.current_buffer != to_be_focused:
                    ui.buffer_focus(to_be_focused)
                else:
                    # refresh an already displayed search
                    ui.current_buffer.rebuild()
                    ui.update()
            else:
                ui.buffer_open(buffers.SearchBuffer(ui, self.query,
                                                    sort_order=self.order))
        else:
            ui.notify('empty query string')


@registerCommand(MODE, 'prompt', arguments=[
    (['startwith'], {'nargs':'?', 'default':'', 'help':'initial content'})])
class PromptCommand(Command):
    """prompts for commandline and interprets it upon select"""
    def __init__(self, startwith='', **kwargs):
        """
        :param startwith: initial content of the prompt widget
        :type startwith: str
        """
        self.startwith = startwith
        Command.__init__(self, **kwargs)

    @inlineCallbacks
    def apply(self, ui):
        logging.info('open command shell')
        mode = ui.mode or 'global'
        cmpl = CommandLineCompleter(ui.dbman, mode, ui.current_buffer)
        cmdline = yield ui.prompt('',
                                  text=self.startwith,
                                  completer=cmpl,
                                  history=ui.commandprompthistory,
                                  )
        logging.debug('CMDLINE: %s' % cmdline)

        # interpret and apply commandline
        if cmdline:
            # save into prompt history
            ui.commandprompthistory.append(cmdline)

            try:
                cmd = commandfactory(cmdline, mode)
                ui.apply_command(cmd)
            except CommandParseError, e:
                ui.notify(e.message, priority='error')


@registerCommand(MODE, 'refresh')
class RefreshCommand(Command):
    """refresh the current buffer"""
    def apply(self, ui):
        ui.current_buffer.rebuild()
        ui.update()


@registerCommand(MODE, 'shellescape', arguments=[
    (['--spawn'], {'action': 'store_true', 'help':'run in terminal window'}),
    (['--thread'], {'action': 'store_true', 'help':'run in separate thread'}),
    (['--refocus'], {'action': 'store_true', 'help':'refocus current buffer \
                     after command has finished'}),
    (['cmd'], {'help':'command line to execute'})],
)
class ExternalCommand(Command):
    """run external command"""
    def __init__(self, cmd, path=None, spawn=False, refocus=True,
                 thread=False, on_success=None, **kwargs):
        """
        :param cmd: the command to call
        :type cmd: str
        :param path: a path to a file (or None)
        :type path: str
        :param spawn: run command in a new terminal
        :type spawn: bool
        :param thread: run asynchronously, don't block alot
        :type thread: bool
        :param refocus: refocus calling buffer after cmd termination
        :type refocus: bool
        :param on_success: code to execute after command successfully exited
        :type on_success: callable
        """
        self.commandstring = cmd
        self.path = path
        self.spawn = spawn
        self.refocus = refocus
        self.in_thread = thread
        self.on_success = on_success
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        callerbuffer = ui.current_buffer

        def afterwards(data):
            if data == 'success':
                if callable(self.on_success):
                    self.on_success()
            else:
                ui.notify(data, priority='error')
            if self.refocus and callerbuffer in ui.buffers:
                logging.info('refocussing')
                ui.buffer_focus(callerbuffer)

        def thread_code(*args):
            if self.path:
                if '{}' in self.commandstring:
                    cmd = self.commandstring.replace('{}',
                            helper.shell_quote(self.path))
                else:
                    cmd = '%s %s' % (self.commandstring,
                                     helper.shell_quote(self.path))
            else:
                cmd = self.commandstring

            if self.spawn:
                cmd = '%s %s' % (settings.get('terminal_cmd'), cmd)
            cmd = cmd.encode('utf-8', errors='ignore')
            logging.info('calling external command: %s' % cmd)
            try:
                if 0 == subprocess.call(shlex.split(cmd)):
                    return 'success'
            except OSError, e:
                return str(e)

        if self.in_thread:
            d = threads.deferToThread(thread_code)
            d.addCallback(afterwards)
        else:
            ui.mainloop.screen.stop()
            ret = thread_code()
            afterwards(ret)
            ui.mainloop.screen.start()


#@registerCommand(MODE, 'edit', arguments=[
#    (['--nospawn'], {'action': 'store_true', 'help':'spawn '}), #todo
#    (['path'], {'help':'file to edit'})]
#]
#)
class EditCommand(ExternalCommand):
    """edit a file"""
    def __init__(self, path, spawn=None, thread=None, **kwargs):
        """
        :param path: path to the file to be edited
        :type path: str
        :param spawn: force running edtor in a new terminal
        :type spawn: bool
        :param thread: run asynchronously, don't block alot
        :type thread: bool
        """
        self.path = path
        self.spawn = settings.get('editor_spawn') or spawn
        if thread != None:
            self.thread = thread
        else:
            self.thread = settings.get('editor_in_thread')

        self.editor_cmd = None
        if os.path.isfile('/usr/bin/editor'):
            self.editor_cmd = '/usr/bin/editor'
        self.editor_cmd = os.environ.get('EDITOR', self.editor_cmd)
        self.editor_cmd = settings.get('editor_cmd') or self.editor_cmd
        logging.debug('using editor_cmd: %s' % self.editor_cmd)

        ExternalCommand.__init__(self, self.editor_cmd, path=self.path,
                                 spawn=self.spawn, thread=self.thread,
                                 **kwargs)

    def apply(self, ui):
        if self.editor_cmd == None:
            ui.notify('no editor set', priority='error')
        else:
            return ExternalCommand.apply(self, ui)


@registerCommand(MODE, 'pyshell')
class PythonShellCommand(Command):
    """open an interactive python shell for introspection"""
    def apply(self, ui):
        ui.mainloop.screen.stop()
        code.interact(local=locals())
        ui.mainloop.screen.start()


@registerCommand(MODE, 'bclose')
class BufferCloseCommand(Command):
    """close a buffer"""
    def __init__(self, buffer=None, **kwargs):
        """
        :param buffer: the buffer to close or None for current
        :type buffer: `alot.buffers.Buffer`
        """
        self.buffer = buffer
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.buffer == None:
            self.buffer = ui.current_buffer
        if len(ui.buffers) == 1:
            if settings.get('quit_on_last_bclose'):
                logging.info('closing the last buffer, exiting')
                ui.apply_command(ExitCommand())
            else:
                logging.info('not closing last remaining buffer as '
                               'global.quit_on_last_bclose is set to False')
        else:
            ui.buffer_close(self.buffer)


@registerCommand(MODE, 'bprevious', forced={'offset': -1},
                 help='focus previous buffer')
@registerCommand(MODE, 'bnext', forced={'offset': +1},
                 help='focus next buffer')
class BufferFocusCommand(Command):
    """focus a :class:`~alot.buffers.Buffer`"""
    def __init__(self, buffer=None, offset=0, **kwargs):
        """
        :param buffer: the buffer to focus or None
        :type buffer: `alot.buffers.Buffer`
        :param offset: position of the buffer to focus relative to the
                       currently focussed one. This is used only if `buffer`
                       is set to `None`
        :type offset: int
        """
        self.buffer = buffer
        self.offset = offset
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.offset:
            idx = ui.buffers.index(ui.current_buffer)
            num = len(ui.buffers)
            self.buffer = ui.buffers[(idx + self.offset) % num]
        ui.buffer_focus(self.buffer)


@registerCommand(MODE, 'bufferlist')
class OpenBufferlistCommand(Command):
    """open a list of active buffers"""
    def __init__(self, filtfun=None, **kwargs):
        """
        :param filtfun: filter to apply to displayed list
        :type filtfun: callable (str->bool)
        """
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        blists = ui.get_buffers_of_type(buffers.BufferlistBuffer)
        if blists:
            ui.buffer_focus(blists[0])
        else:
            bl = buffers.BufferlistBuffer(ui, self.filtfun)
            ui.buffer_open(bl)


@registerCommand(MODE, 'taglist')
class TagListCommand(Command):
    """opens taglist buffer"""
    def __init__(self, filtfun=None, **kwargs):
        """
        :param filtfun: filter to apply to displayed list
        :type filtfun: callable (str->bool)
        """
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        tags = ui.dbman.get_all_tags()
        blists = ui.get_buffers_of_type(buffers.TagListBuffer)
        if blists:
            buf = blists[0]
            buf.tags = tags
            buf.rebuild()
            ui.buffer_focus(buf)
        else:
            ui.buffer_open(buffers.TagListBuffer(ui, tags, self.filtfun))


@registerCommand(MODE, 'flush')
class FlushCommand(Command):
    """flush write operations or retry until committed"""
    def apply(self, ui):
        try:
            ui.dbman.flush()
        except DatabaseLockedError:
            timeout = settings.get('flush_retry_timeout')

            def f(*args):
                self.apply(ui)
            ui.mainloop.set_alarm_in(timeout, f)
            ui.notify('index locked, will try again in %d secs' % timeout)
            ui.update()
            return
        logging.debug('flush complete')


#TODO: choices
@registerCommand(MODE, 'help', arguments=[
    (['commandname'], {'help':'command or \'bindings\''})])
class HelpCommand(Command):
    """
    display help for a command. Use \'bindings\' to
    display all keybings interpreted in current mode.'
    """
    def __init__(self, commandname='', **kwargs):
        """
        :param commandname: command to document
        :type commandname: str
        """
        Command.__init__(self, **kwargs)
        self.commandname = commandname

    def apply(self, ui):
        logging.debug('HELP')
        if self.commandname == 'bindings':
            text_att = settings.get_theming_attribute('help', 'text')
            title_att = settings.get_theming_attribute('help', 'title')
            section_att = settings.get_theming_attribute('help', 'section')
            # get mappings
            if ui.mode in settings._bindings:
                modemaps = dict(settings._bindings[ui.mode].items())
            else:
                modemaps = {}
            is_scalar = lambda (k, v): k in settings._bindings.scalars
            globalmaps = dict(filter(is_scalar, settings._bindings.items()))

            # build table
            maxkeylength = len(max((modemaps).keys() + globalmaps.keys(),
                                   key=len))
            keycolumnwidth = maxkeylength + 2

            linewidgets = []
            # mode specific maps
            if modemaps:
                linewidgets.append(urwid.Text((section_att,
                                    '\n%s-mode specific maps' % ui.mode)))
                for (k, v) in modemaps.items():
                    line = urwid.Columns([('fixed', keycolumnwidth,
                                           urwid.Text((text_att, k))),
                                          urwid.Text((text_att, v))])
                    linewidgets.append(line)

            # global maps
            linewidgets.append(urwid.Text((section_att, '\nglobal maps')))
            for (k, v) in globalmaps.items():
                if k not in modemaps:
                    line = urwid.Columns(
                        [('fixed', keycolumnwidth, urwid.Text((text_att, k))),
                         urwid.Text((text_att, v))])
                    linewidgets.append(line)

            body = urwid.ListBox(linewidgets)
            ckey = 'cancel'
            titletext = 'Bindings Help (%s cancels)' % ckey

            box = widgets.DialogBox(body, titletext,
                                    bodyattr=text_att,
                                    titleattr=title_att)

            # put promptwidget as overlay on main widget
            overlay = urwid.Overlay(box, ui.mainframe, 'center',
                                    ('relative', 70), 'middle',
                                    ('relative', 70))
            ui.show_as_root_until_keypress(overlay, 'cancel')
        else:
            logging.debug('HELP %s' % self.commandname)
            parser = commands.lookup_parser(self.commandname, ui.mode)
            if parser:
                ui.notify(parser.format_help(), block=True)
            else:
                ui.notify('command not known: %s' % self.commandname,
                          priority='error')


@registerCommand(MODE, 'compose', arguments=[
    (['--sender'], {'nargs': '?', 'help':'sender'}),
    (['--template'], {'nargs':'?',
                      'help':'path to a template message file'}),
    (['--subject'], {'nargs':'?', 'help':'subject line'}),
    (['--to'], {'nargs':'+', 'help':'recipients'}),
    (['--cc'], {'nargs':'+', 'help':'copy to'}),
    (['--bcc'], {'nargs':'+', 'help':'blind copy to'}),
    (['--attach'], {'nargs':'+', 'help':'attach files'}),
    (['--omit_signature'], {'action': 'store_true',
                            'help':'do not add signature'}),
    (['--spawn'], {'action': 'store_true',
                   'help':'spawn editor in new terminal'}),
])
class ComposeCommand(Command):
    """compose a new email"""
    def __init__(self, envelope=None, headers={}, template=None,
                 sender=u'', subject=u'', to=[], cc=[], bcc=[], attach=None,
                 omit_signature=False, spawn=None, **kwargs):
        """
        :param envelope: use existing envelope
        :type envelope: :class:`~alot.db.envelope.Envelope`
        :param headers: forced header values
        :type header: doct (str->str)
        :param template: name of template to parse into the envelope after
                         creation. This should be the name of a file in your
                         template_dir
        :type template: str
        :param sender: From-header value
        :type sender: str
        :param subject: Subject-header value
        :type subject: str
        :param to: To-header value
        :type to: str
        :param cc: Cc-header value
        :type cc: str
        :param bcc: Bcc-header value
        :type bcc: str
        :param attach: Path to files to be attached (globable)
        :type attach: str
        :param omit_signature: do not attach/append signature
        :type omit_signature: bool
        :param spawn: force spawning of editor in a new terminal
        :type spawn: bool
        """

        Command.__init__(self, **kwargs)

        self.envelope = envelope
        self.template = template
        self.headers = headers
        self.sender = sender
        self.subject = subject
        self.to = to
        self.cc = cc
        self.bcc = bcc
        self.attach = attach
        self.omit_signature = omit_signature
        self.force_spawn = spawn

    @inlineCallbacks
    def apply(self, ui):
        if self.envelope == None:
            self.envelope = Envelope()
        if self.template is not None:
            #get location of tempsdir, containing msg templates
            tempdir = settings.get('template_dir')
            tempdir = os.path.expanduser(tempdir)
            if not tempdir:
                xdgdir = os.environ.get('XDG_CONFIG_HOME',
                                        os.path.expanduser('~/.config'))
                tempdir = os.path.join(xdgdir, 'alot', 'templates')

            path = os.path.expanduser(self.template)
            if not os.path.dirname(path):  # use tempsdir
                if not os.path.isdir(tempdir):
                    ui.notify('no templates directory: %s' % tempdir,
                              priority='error')
                    return
                path = os.path.join(tempdir, path)

            if not os.path.isfile(path):
                ui.notify('could not find template: %s' % path,
                          priority='error')
                return
            try:
                self.envelope.parse_template(open(path).read())
            except Exception, e:
                ui.notify(str(e), priority='error')
                return

        # set forced headers
        for key, value in self.headers.items():
            self.envelope.add(key, value)

        # set forced headers for separate parameters
        if self.sender:
            self.envelope.add('From', self.sender)
        if self.subject:
            self.envelope.add('Subject', self.subject)
        if self.to:
            self.envelope.add('To', ','.join(self.to))
        if self.cc:
            self.envelope.add('Cc', ','.join(self.cc))
        if self.bcc:
            self.envelope.add('Bcc', ','.join(self.bcc))

        # get missing From header
        if not 'From' in self.envelope.headers:
            accounts = settings.get_accounts()
            if len(accounts) == 1:
                a = accounts[0]
                fromstring = "%s <%s>" % (a.realname, a.address)
                self.envelope.add('From', fromstring)
            else:
                cmpl = AccountCompleter()
                fromaddress = yield ui.prompt('From', completer=cmpl,
                                              tab=1)
                if fromaddress is None:
                    ui.notify('canceled')
                    return
                a = settings.get_account_by_address(fromaddress)
                if a is not None:
                    fromstring = "%s <%s>" % (a.realname, a.address)
                    self.envelope.add('From', fromstring)
                else:
                    self.envelope.add('From', fromaddress)

        # add signature
        if not self.omit_signature:
            name, addr = email.Utils.parseaddr(self.envelope['From'])
            account = settings.get_account_by_address(addr)
            if account is not None:
                if account.signature:
                    logging.debug('has signature')
                    sig = os.path.expanduser(account.signature)
                    if os.path.isfile(sig):
                        logging.debug('is file')
                        if account.signature_as_attachment:
                            name = account.signature_filename or None
                            self.envelope.attach(sig, filename=name)
                            logging.debug('attached')
                        else:
                            sigcontent = open(sig).read()
                            enc = helper.guess_encoding(sigcontent)
                            mimetype = helper.guess_mimetype(sigcontent)
                            if mimetype.startswith('text'):
                                sigcontent = helper.string_decode(sigcontent,
                                                                  enc)
                                self.envelope.body += '\n' + sigcontent
                    else:
                        ui.notify('could not locate signature: %s' % sig,
                                  priority='error')
                        if (yield ui.choice('send without signature',
                                        select='yes', cancel='no')) == 'no':
                            return

        # Figure out whether we should GPG sign messages by default
        # and look up key if so
        sender = self.envelope.get('From')
        name, addr = email.Utils.parseaddr(sender)
        account = settings.get_account_by_address(addr)
        self.envelope.sign = account.sign_by_default
        self.envelope.sign_key = account.gpg_key

        # get missing To header
        if 'To' not in self.envelope.headers:
            allbooks = not settings.get('complete_matching_abook_only')
            logging.debug(allbooks)
            if account is not None:
                abooks = settings.get_addressbooks(order=[account],
                                                    append_remaining=allbooks)
                logging.debug(abooks)
                completer = ContactsCompleter(abooks)
            else:
                completer = None
            to = yield ui.prompt('To',
                                 completer=completer)
            if to == None:
                ui.notify('canceled')
                return
            self.envelope.add('To', to.strip(' \t\n,'))

        if settings.get('ask_subject') and \
           not 'Subject' in self.envelope.headers:
            subject = yield ui.prompt('Subject')
            logging.debug('SUBJECT: "%s"' % subject)
            if subject == None:
                ui.notify('canceled')
                return
            self.envelope.add('Subject', subject)

        if self.attach:
            for gpath in self.attach:
                for a in glob.glob(gpath):
                    self.envelope.attach(a)
                    logging.debug('attaching: ' + a)

        cmd = commands.envelope.EditCommand(envelope=self.envelope,
                spawn=self.force_spawn, refocus=False)
        ui.apply_command(cmd)


@registerCommand(MODE, 'move', help='move focus', arguments=[
    (['key'], {'nargs':'+', 'help':'direction'})])
@registerCommand(MODE, 'cancel', help='send cancel event',
                 forced={'key': 'cancel'})
@registerCommand(MODE, 'select', help='send select event',
                 forced={'key': 'select'})
class SendKeypressCommand(Command):
    """send a keypress to the main widget to be processed by urwid"""
    def __init__(self, key, **kwargs):
        Command.__init__(self, **kwargs)
        if isinstance(key, list):
            key = ' '.join(key)
        self.key = key

    def apply(self, ui):
        ui.keypress(self.key)
