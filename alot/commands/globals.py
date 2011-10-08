from commands import Command, registerCommand
from twisted.internet import defer

registerCommand('global', 'exit', {})
class ExitCommand(Command):
    """shuts the MUA down cleanly"""
    @defer.inlineCallbacks
    def apply(self, ui):
        if settings.config.getboolean('general', 'bug_on_exit'):
            if (yield ui.choice('realy quit?', select='yes', cancel='no',
                               msg_position='left')) == 'no':
                return
        ui.exit()


class SearchCommand(Command):
    """open a new search buffer"""
    def __init__(self, query, **kwargs):
        """
        :param query: initial querystring
        """
        self.query = query
        Command.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def apply(self, ui):
        if self.query:
            if self.query == '*' and ui.current_buffer:
                s = 'really search for all threads? This takes a while..'
                if (yield ui.choice(s, select='yes', cancel='no')) == 'no':
                    return
            open_searches = ui.get_buffers_of_type(buffer.SearchBuffer)
            to_be_focused = None
            for sb in open_searches:
                if sb.querystring == self.query:
                    to_be_focused = sb
            if to_be_focused:
                ui.buffer_focus(to_be_focused)
            else:
                ui.buffer_open(buffer.SearchBuffer(ui, self.query))
        else:
            ui.notify('empty query string')


class PromptCommand(Command):
    """starts commandprompt"""
    def __init__(self, startstring=u'', **kwargs):
        self.startstring = startstring
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ui.commandprompt(self.startstring)


class RefreshCommand(Command):
    """refreshes the current buffer"""
    def apply(self, ui):
        ui.current_buffer.rebuild()
        ui.update()


class PythonShellCommand(Command):
    """opens an interactive shell for introspection"""
    def apply(self, ui):
        ui.mainloop.screen.stop()
        code.interact(local=locals())
        ui.mainloop.screen.start()


class BufferCloseCommand(Command):
    """close a buffer"""
    def __init__(self, buffer=None, focussed=False, **kwargs):
        """
        :param buffer: the selected buffer
        :type buffer: `alot.buffer.Buffer`
        """
        self.buffer = buffer
        self.focussed = focussed
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.focussed:
            #if in bufferlist, this is ugly.
            self.buffer = ui.current_buffer.get_selected_buffer()
        elif not self.buffer:
            self.buffer = ui.current_buffer
        ui.buffer_close(self.buffer)
        ui.buffer_focus(ui.current_buffer)


class OpenBufferlistCommand(Command):
    """open a bufferlist buffer"""
    def __init__(self, filtfun=None, **kwargs):
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        blists = ui.get_buffers_of_type(buffer.BufferlistBuffer)
        if blists:
            ui.buffer_focus(blists[0])
        else:
            ui.buffer_open(buffer.BufferlistBuffer(ui, self.filtfun))


class TagListCommand(Command):
    """open a taglisat buffer"""
    def __init__(self, filtfun=None, **kwargs):
        self.filtfun = filtfun
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        tags = ui.dbman.get_all_tags()
        buf = buffer.TagListBuffer(ui, tags, self.filtfun)
        ui.buffers.append(buf)
        buf.rebuild()
        ui.buffer_focus(buf)


class FlushCommand(Command):
    """Flushes writes to the index. Retries until committed"""
    def apply(self, ui):
        try:
            ui.dbman.flush()
        except DatabaseLockedError:
            timeout = settings.config.getint('general', 'flush_retry_timeout')

            def f(*args):
                self.apply(ui)
            ui.mainloop.set_alarm_in(timeout, f)
            ui.notify('index locked, will try again in %d secs' % timeout)
            ui.update()
            return


class ComposeCommand(Command):
    """compose a new email and open an envelope for it"""
    def __init__(self, mail=None, headers={}, **kwargs):
        Command.__init__(self, **kwargs)
        if not mail:
            self.mail = MIMEMultipart()
            self.mail.attach(MIMEText('', 'plain', 'UTF-8'))
        else:
            self.mail = mail
        for key, value in headers.items():
            self.mail[key] = encode_header(key, value)

    @defer.inlineCallbacks
    def apply(self, ui):
        # TODO: fill with default header (per account)
        # get From header
        if not 'From' in self.mail:
            accounts = ui.accountman.get_accounts()
            if len(accounts) == 0:
                ui.notify('no accounts set')
                return
            elif len(accounts) == 1:
                a = accounts[0]
            else:
                cmpl = AccountCompleter(ui.accountman)
                fromaddress = yield ui.prompt(prefix='From>', completer=cmpl,
                                              tab=1)
                validaddresses = [a.address for a in accounts] + [None]
                while fromaddress not in validaddresses:  # TODO: not cool
                    ui.notify('no account for this address. (<esc> cancels)')
                    fromaddress = yield ui.prompt(prefix='From>',
                                                  completer=cmpl)
                if not fromaddress:
                    ui.notify('canceled')
                    return
                a = ui.accountman.get_account_by_address(fromaddress)
            self.mail['From'] = "%s <%s>" % (a.realname, a.address)

        #get To header
        if 'To' not in self.mail:
            name, addr = email.Utils.parseaddr(unicode(self.mail.get('From')))
            a = ui.accountman.get_account_by_address(addr)

            allbooks = not settings.config.getboolean('general',
                                'complete_matching_abook_only')
            ui.logger.debug(allbooks)
            abooks = ui.accountman.get_addressbooks(order=[a],
                                                    append_remaining=allbooks)
            ui.logger.debug(abooks)
            to = yield ui.prompt(prefix='To>',
                                 completer=ContactsCompleter(abooks))
            if to == None:
                ui.notify('canceled')
                return
            self.mail['To'] = encode_header('to', to)
        if settings.config.getboolean('general', 'ask_subject') and \
           not 'Subject' in self.mail:
            subject = yield ui.prompt(prefix='Subject>')
            if subject == None:
                ui.notify('canceled')
                return
            self.mail['Subject'] = encode_header('subject', subject)

        ui.apply_command(EnvelopeEditCommand(mail=self.mail))


class EnvelopeOpenCommand(Command):
    """open a new envelope buffer"""
    def __init__(self, mail=None, **kwargs):
        self.mail = mail
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ui.buffer_open(buffer.EnvelopeBuffer(ui, mail=self.mail))


class SendKeypressCommand(Command):
    def __init__(self, key, **kwargs):
        Command.__init__(self, **kwargs)
        self.key = key

    def apply(self, ui):
        ui.keypress(self.key)


class HelpCommand(Command):
    def __init__(self, commandline='', **kwargs):
        Command.__init__(self, **kwargs)
        self.commandline = commandline.strip()

    def apply(self, ui):
        if self.commandline:
            cmd = self.commandline.split(' ', 1)[0]
            # TODO: how to I access COMMANDS from below?
            ui.notify('no help for \'%s\'' % cmd, priority='error')
            titletext = 'help for %s' % cmd
            body = urwid.Text('helpstring')
            return
        else:
            # get mappings
            modemaps = dict(settings.config.items('%s-maps' % ui.mode))
            globalmaps = dict(settings.config.items('global-maps'))

            # build table
            maxkeylength = len(max((modemaps).keys() + globalmaps.keys(),
                                   key=len))
            keycolumnwidth = maxkeylength + 2

            linewidgets = []
            # mode specific maps
            linewidgets.append(urwid.Text(('helptexth1',
                                '\n%s-mode specific maps' % ui.mode)))
            for (k, v) in modemaps.items():
                line = urwid.Columns([('fixed', keycolumnwidth, urwid.Text(k)),
                                      urwid.Text(v)])
                linewidgets.append(line)

            # global maps
            linewidgets.append(urwid.Text(('helptexth1',
                                           '\nglobal maps')))
            for (k, v) in globalmaps.items():
                if k not in modemaps:
                    line = urwid.Columns(
                        [('fixed', keycolumnwidth, urwid.Text(k)),
                         urwid.Text(v)])
                    linewidgets.append(line)

            body = urwid.ListBox(linewidgets)
            ckey = 'cancel'
            titletext = 'Bindings Help (%s cancels)' % ckey

        box = widgets.DialogBox(body, titletext,
                                bodyattr='helptext',
                                titleattr='helptitle')

        # put promptwidget as overlay on main widget
        overlay = urwid.Overlay(box, ui.mainframe, 'center',
                                ('relative', 70), 'middle',
                                ('relative', 70))
        ui.show_as_root_until_keypress(overlay, 'cancel')


class ExternalCommand(Command):
    """calls external command"""
    def __init__(self, commandstring, path=None, spawn=False, refocus=True,
                 in_thread=False, on_success=None, **kwargs):
        """
        :param commandstring: the command to call
        :type commandstring: str
        :param path: a path to a file (or None)
        :type path: str
        :param spawn: run command in a new terminal
        :type spawn: boolean
        :param in_thread: run asynchronously, don't block alot
        :type in_thread: boolean
        :param refocus: refocus calling buffer after cmd termination
        :type refocus: boolean
        :param on_success: code to execute after command successfully exited
        :type on_success: callable
        """
        self.commandstring = commandstring
        self.path = path
        self.spawn = spawn
        self.refocus = refocus
        self.in_thread = in_thread
        self.on_success = on_success
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        callerbuffer = ui.current_buffer

        def afterwards(data):
            if callable(self.on_success) and data == 'success':
                self.on_success()
            if self.refocus and callerbuffer in ui.buffers:
                ui.logger.info('refocussing')
                ui.buffer_focus(callerbuffer)

        write_fd = ui.mainloop.watch_pipe(afterwards)

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
                cmd = '%s %s' % (settings.config.get('general',
                                                      'terminal_cmd'),
                                  cmd)
            cmd = cmd.encode('ascii', errors='ignore')
            ui.logger.info('calling external command: %s' % cmd)
            returncode = subprocess.call(shlex.split(cmd))
            if returncode == 0:
                os.write(write_fd, 'success')

        if self.in_thread:
            thread = threading.Thread(target=thread_code)
            thread.start()
        else:
            ui.mainloop.screen.stop()
            thread_code()
            ui.mainloop.screen.start()


class EditCommand(ExternalCommand):
    def __init__(self, path, spawn=None, **kwargs):
        self.path = path
        if spawn != None:
            self.spawn = spawn
        else:
            self.spawn = settings.config.getboolean('general', 'spawn_editor')
        editor_cmd = settings.config.get('general', 'editor_cmd')

        ExternalCommand.__init__(self, editor_cmd, path=self.path,
                                 spawn=self.spawn, in_thread=self.spawn,
                                 **kwargs)


class BufferFocusCommand(Command):
    """focus a buffer"""
    def __init__(self, buffer=None, offset=0, **kwargs):
        """
        :param buffer: the buffer to focus
        :type buffer: `alot.buffer.Buffer`
        """
        self.buffer = buffer
        self.offset = offset
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.offset:
            idx = ui.buffers.index(ui.current_buffer)
            num = len(ui.buffers)
            self.buffer = ui.buffers[(idx + self.offset) % num]
        else:
            if not self.buffer:
                self.buffer = ui.current_buffer.get_selected_buffer()
        ui.buffer_focus(self.buffer)
