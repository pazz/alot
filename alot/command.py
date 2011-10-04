"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Alot is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
import os
import re
import code
import glob
import logging
import threading
import subprocess
import shlex
import email
import tempfile
from email import Charset
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urwid
from twisted.internet import defer

import buffer
import settings
import widgets
import completion
import helper
from db import DatabaseROError
from db import DatabaseLockedError
from completion import ContactsCompleter
from completion import AccountCompleter
from message import decode_to_unicode
from message import decode_header
from message import encode_header


class Command(object):
    """base class for commands"""
    def __init__(self, prehook=None, posthook=None):
        self.prehook = prehook
        self.posthook = posthook
        self.undoable = False
        self.help = self.__doc__

    def apply(self, caller):
        pass


class ExitCommand(Command):
    """shuts the MUA down cleanly"""
    @defer.inlineCallbacks
    def apply(self, ui):
        if settings.config.getboolean('general', 'bug_on_exit'):
            if (yield ui.choice('realy quit?', select='yes', cancel='no',
                               msg_position='left')) == 'no':
                return
        ui.exit()


class OpenThreadCommand(Command):
    """open a new thread-view buffer"""
    def __init__(self, thread=None, **kwargs):
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        if self.thread:
            query = ui.current_buffer.querystring
            ui.logger.info('open thread view for %s' % self.thread)

            sb = buffer.ThreadBuffer(ui, self.thread)
            ui.buffer_open(sb)
            sb.unfold_matching(query)


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


class ToggleThreadTagCommand(Command):
    """toggles tag in given or currently selected thread"""
    def __init__(self, tags, thread=None, **kwargs):
        assert tags
        self.thread = thread
        self.tags = set(tags)
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        if not self.thread:
            return
        try:
            self.thread.set_tags(set(self.thread.get_tags()) ^ self.tags)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        # flush index
        ui.apply_command(FlushCommand())

        # update current buffer
        # TODO: what if changes not yet flushed?
        cb = ui.current_buffer
        if isinstance(cb, buffer.SearchBuffer):
            # refresh selected threadline
            threadwidget = cb.get_selected_threadline()
            threadwidget.rebuild()  # rebuild and redraw the line
            #remove line from searchlist if thread doesn't match the query
            qs = "(%s) AND thread:%s" % (cb.querystring,
                                         self.thread.get_thread_id())
            if ui.dbman.count_messages(qs) == 0:
                ui.logger.debug('remove: %s' % self.thread)
                cb.threadlist.remove(threadwidget)
                cb.result_count -= self.thread.get_total_messages()
                ui.update()
        elif isinstance(cb, buffer.ThreadBuffer):
            pass


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


# SEARCH
class RetagPromptCommand(Command):
    """start a commandprompt to retag selected threads' tags
    this is needed to fill the prompt with the current tags..
    """
    def apply(self, ui):
        thread = ui.current_buffer.get_selected_thread()
        if not thread:
            return
        initial_tagstring = ','.join(thread.get_tags())
        ui.commandprompt('retag ' + initial_tagstring)


class RetagCommand(Command):
    """tag selected thread"""
    def __init__(self, tagsstring=u'', thread=None, **kwargs):
        self.tagsstring = tagsstring
        self.thread = thread
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.thread:
            self.thread = ui.current_buffer.get_selected_thread()
        if not self.thread:
            return
        tags = filter(lambda x: x, self.tagsstring.split(','))
        ui.logger.info("got %s:%s" % (self.tagsstring, tags))
        try:
            self.thread.set_tags(tags)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        # flush index
        ui.apply_command(FlushCommand())

        # refresh selected threadline
        sbuffer = ui.current_buffer
        threadwidget = sbuffer.get_selected_threadline()
        threadwidget.rebuild()  # rebuild and redraw the line


class RefineCommand(Command):
    """refine the query of the currently open searchbuffer"""
    def __init__(self, query=None, **kwargs):
        self.querystring = query
        Command.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def apply(self, ui):
        if self.querystring:
            if self.querystring == '*':
                s = 'really search for all threads? This takes a while..'
                if (yield ui.choice(s, select='yes', cancel='no')) == 'no':
                    return
            sbuffer = ui.current_buffer
            oldquery = sbuffer.querystring
            if self.querystring not in [None, oldquery]:
                sbuffer.querystring = self.querystring
                sbuffer = ui.current_buffer
                sbuffer.rebuild()
                ui.update()
        else:
            ui.notify('empty query string')


class RefinePromptCommand(Command):
    """prompt to change current search buffers query"""
    def apply(self, ui):
        sbuffer = ui.current_buffer
        oldquery = sbuffer.querystring
        ui.commandprompt('refine ' + oldquery)


# THREAD
class ReplyCommand(Command):
    """format reply for currently selected message and open envelope for it"""
    def __init__(self, message=None, groupreply=False, **kwargs):
        """
        :param message: the original message to reply to
        :type message: `alot.message.Message`
        :param groupreply: copy other recipients from Bcc/Cc/To to the reply
        :type groupreply: boolean
        """
        self.message = message
        self.groupreply = groupreply
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.message:
            self.message = ui.current_buffer.get_selected_message()
        mail = self.message.get_email()
        # set body text
        name, address = self.message.get_author()
        timestamp = self.message.get_date()
        qf = settings.hooks.get('reply_prefix')
        if qf:
            quotestring = qf(name, address, timestamp,
                             ui=ui, dbm=ui.dbman, aman=ui.accountman,
                             log=ui.logger, config=settings.config)
        else:
            quotestring = 'Quoting %s (%s)\n' % (name, timestamp)
        mailcontent = quotestring
        for line in self.message.accumulate_body().splitlines():
            mailcontent += '>' + line + '\n'

        Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')
        bodypart = MIMEText(mailcontent.encode('utf-8'), 'plain', 'UTF-8')
        reply = MIMEMultipart()
        reply.attach(bodypart)

        # copy subject
        subject = mail.get('Subject', '')
        if not subject.startswith('Re:'):
            subject = 'Re: ' + subject
        reply['Subject'] = Header(subject.encode('utf-8'), 'UTF-8').encode()

        # set From
        my_addresses = ui.accountman.get_addresses()
        matched_address = ''
        in_to = [a for a in my_addresses if a in mail.get('To', '')]
        if in_to:
            matched_address = in_to[0]
        else:
            cc = mail.get('Cc', '') + mail.get('Bcc', '')
            in_cc = [a for a in my_addresses if a in cc]
            if in_cc:
                matched_address = in_cc[0]
        if matched_address:
            account = ui.accountman.get_account_by_address(matched_address)
            fromstring = '%s <%s>' % (account.realname, account.address)
            reply['From'] = encode_header('From', fromstring)

        # set To
        del(reply['To'])
        if self.groupreply:
            cleared = self.clear_my_address(my_addresses, mail.get('To', ''))
            if cleared:
                logging.info(mail['From'] + ', ' + cleared)
                to = mail['From'] + ', ' + cleared
                reply['To'] = encode_header('To', to)
                logging.info(reply['To'])
            else:
                reply['To'] = encode_header('To', mail['From'])
            # copy cc and bcc for group-replies
            if 'Cc' in mail:
                cc = self.clear_my_address(my_addresses, mail['Cc'])
                reply['Cc'] = encode_header('Cc', cc)
            if 'Bcc' in mail:
                bcc = self.clear_my_address(my_addresses, mail['Bcc'])
                reply['Bcc'] = encode_header('Bcc', bcc)
        else:
            reply['To'] = encode_header('To', mail['From'])

        # set In-Reply-To header
        del(reply['In-Reply-To'])
        reply['In-Reply-To'] = '<%s>' % self.message.get_message_id()

        # set References header
        old_references = mail.get('References', '')
        if old_references:
            old_references = old_references.split()
            references = old_references[-8:]
            if len(old_references) > 8:
                references = old_references[:1] + references
            references.append('<%s>' % self.message.get_message_id())
            reply['References'] = ' '.join(references)
        else:
            reply['References'] = '<%s>' % self.message.get_message_id()

        ui.apply_command(ComposeCommand(mail=reply))

    def clear_my_address(self, my_addresses, value):
        new_value = []
        for entry in value.split(','):
            if not [a for a in my_addresses if a in entry]:
                new_value.append(entry.strip())
        return ', '.join(new_value)


class ForwardCommand(Command):
    def __init__(self, message=None, inline=False, **kwargs):
        """
        :param message: the original message to forward. If None, the currently
                        selected one is used
        :type message: `alot.message.Message`
        :param inline: Copy originals body text instead of attaching the whole
                       mail
        :type inline: boolean
        """
        self.message = message
        self.inline = inline
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.message:
            self.message = ui.current_buffer.get_selected_message()
        mail = self.message.get_email()

        reply = MIMEMultipart()
        Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')
        if self.inline:  # inline mode
            # set body text
            name, address = self.message.get_author()
            timestamp = self.message.get_date()
            qf = settings.hooks.get('forward_prefix')
            if qf:
                quote = qf(name, address, timestamp,
                             ui=ui, dbm=ui.dbman, aman=ui.accountman,
                             log=ui.logger, config=settings.config)
            else:
                quote = 'Forwarded message from %s (%s):\n' % (name, timestamp)
            mailcontent = quote
            for line in self.message.accumulate_body().splitlines():
                mailcontent += '>' + line + '\n'

            bodypart = MIMEText(mailcontent.encode('utf-8'), 'plain', 'UTF-8')
            reply.attach(bodypart)

        else:  # attach original mode
            # create empty text msg
            bodypart = MIMEText('', 'plain', 'UTF-8')
            reply.attach(bodypart)
            # attach original msg
            reply.attach(mail)

        # copy subject
        subject = mail.get('Subject', '')
        subject = 'Fwd: ' + subject
        reply['Subject'] = Header(subject.encode('utf-8'), 'UTF-8').encode()

        # set From
        my_addresses = ui.accountman.get_addresses()
        matched_address = ''
        in_to = [a for a in my_addresses if a in mail.get('To', '')]
        if in_to:
            matched_address = in_to[0]
        else:
            cc = mail.get('Cc', '') + mail.get('Bcc', '')
            in_cc = [a for a in my_addresses if a in cc]
            if in_cc:
                matched_address = in_cc[0]
        if matched_address:
            account = ui.accountman.get_account_by_address(matched_address)
            fromstring = '%s <%s>' % (account.realname, account.address)
            reply['From'] = encode_header('From', fromstring)
        ui.apply_command(ComposeCommand(mail=reply))


class FoldMessagesCommand(Command):
    def __init__(self, all=False, visible=None, **kwargs):
        self.all = all
        self.visible = visible
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        lines = []
        if not self.all:
            lines.append(ui.current_buffer.get_selection())
        else:
            lines = ui.current_buffer.get_message_widgets()

        for widget in lines:
            # in case the thread is yet unread, remove this tag
            msg = widget.get_message()
            if self.visible or (self.visible == None and widget.folded):
                if 'unread' in msg.get_tags():
                    msg.remove_tags(['unread'])
                    ui.apply_command(FlushCommand())
                    widget.rebuild()
                widget.fold(visible=True)
            else:
                widget.fold(visible=False)


class ToggleHeaderCommand(Command):
    def apply(self, ui):
        msgw = ui.current_buffer.get_selection()
        msgw.toggle_full_header()


class PipeCommand(Command):
    def __init__(self, command, whole_thread=False, separately=False,
                 noop_msg='no command specified', confirm_msg='',
                 done_msg='done', **kwargs):
        Command.__init__(self, **kwargs)
        self.cmd = command
        self.whole_thread = whole_thread
        self.separately = separately
        self.noop_msg = noop_msg
        self.confirm_msg = confirm_msg
        self.done_msg = done_msg

    @defer.inlineCallbacks
    def apply(self, ui):
        # abort if command unset
        if not self.cmd:
            ui.notify(self.noop_msg, priority='error')
            return

        # get messages to pipe
        if self.whole_thread:
            thread = ui.current_buffer.get_selected_thread()
            if not thread:
                return
            to_print = thread.get_messages().keys()
        else:
            to_print = [ui.current_buffer.get_selected_message()]

        # ask for confirmation if needed
        if self.confirm_msg:
            if (yield ui.choice(self.confirm_msg, select='yes',
                                cancel='no')) == 'no':
                return

        # prepare message sources
        mailstrings = [m.get_email().as_string() for m in to_print]
        if not self.separately:
            mailstrings = ['\n\n'.join(mailstrings)]

        # do teh monkey
        for mail in mailstrings:
            out, err = helper.pipe_to_command(self.cmd, mail)
            if err:
                ui.notify(err, priority='error')
                return

        # display 'done' message
        if self.done_msg:
            ui.notify(self.done_msg)


class PrintCommand(PipeCommand):
    def __init__(self, whole_thread=False, separately=False, **kwargs):
        # get print command
        cmd = settings.config.get('general', 'print_cmd', fallback='')

        # set up notification strings
        if whole_thread:
            confirm_msg = 'print all messages in thread?'
            ok_msg = 'printed thread using %s' % cmd
        else:
            confirm_msg = 'print selected message?'
            ok_msg = 'printed message using %s' % cmd

        # no print cmd set
        noop_msg = 'no print command specified. Set "print_cmd" in the '\
                    'global section.'
        PipeCommand.__init__(self, cmd, whole_thread=whole_thread,
                             separately=separately,
                             noop_msg=noop_msg, confirm_msg=confirm_msg,
                             done_msg=ok_msg, **kwargs)


class SaveAttachmentCommand(Command):
    def __init__(self, all=False, path=None, **kwargs):
        Command.__init__(self, **kwargs)
        self.all = all
        self.path = path

    @defer.inlineCallbacks
    def apply(self, ui):
        pcomplete = completion.PathCompleter()
        if self.all:
            msg = ui.current_buffer.get_selected_message()
            if not self.path:
                self.path = yield ui.prompt(prefix='save attachments to:',
                                      text=os.path.join('~', ''),
                                      completer=pcomplete)
            if self.path:
                if os.path.isdir(os.path.expanduser(self.path)):
                    for a in msg.get_attachments():
                        dest = a.save(self.path)
                        name = a.get_filename()
                        if name:
                            ui.notify('saved %s as: %s' % (name, dest))
                        else:
                            ui.notify('saved attachment as: %s' % dest)
                else:
                    ui.notify('not a directory: %s' % self.path,
                              priority='error')
            else:
                ui.notify('canceled')
        else:  # save focussed attachment
            focus = ui.get_deep_focus()
            if isinstance(focus, widgets.AttachmentWidget):
                attachment = focus.get_attachment()
                filename = attachment.get_filename()
                if not self.path:
                    msg = 'save attachment (%s) to:' % filename
                    initialtext = os.path.join('~', filename)
                    self.path = yield ui.prompt(prefix=msg,
                                                completer=pcomplete,
                                                text=initialtext)
                if self.path:
                    try:
                        dest = attachment.save(self.path)
                        ui.notify('saved attachment as: %s' % dest)
                    except (IOError, OSError), e:
                        ui.notify(str(e), priority='error')
                else:
                    ui.notify('canceled')


class OpenAttachmentCommand(Command):
    """displays an attachment according to mailcap"""
    def __init__(self, attachment, **kwargs):
        Command.__init__(self, **kwargs)
        self.attachment = attachment

    def apply(self, ui):
        logging.info('open attachment')
        mimetype = self.attachment.get_content_type()
        handler = settings.get_mime_handler(mimetype)
        if handler:
            path = self.attachment.save(tempfile.gettempdir())
            handler = handler.replace('\'%s\'', '{}')

            def afterwards():
                os.remove(path)
            ui.apply_command(ExternalCommand(handler, path=path,
                                             on_success=afterwards,
                                             in_thread=True))
        else:
            ui.notify('unknown mime type')


class ThreadSelectCommand(Command):
    def apply(self, ui):
        focus = ui.get_deep_focus()
        if isinstance(focus, widgets.MessageSummaryWidget):
            ui.apply_command(FoldMessagesCommand())
        elif isinstance(focus, widgets.AttachmentWidget):
            logging.info('open attachment')
            ui.apply_command(OpenAttachmentCommand(focus.get_attachment()))
        else:
            logging.info('unknown widget %s' % focus)


### ENVELOPE
class EnvelopeOpenCommand(Command):
    """open a new envelope buffer"""
    def __init__(self, mail=None, **kwargs):
        self.mail = mail
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ui.buffer_open(buffer.EnvelopeBuffer(ui, mail=self.mail))


class EnvelopeEditCommand(Command):
    """re-edits mail in from envelope buffer"""
    def __init__(self, mail=None, **kwargs):
        self.mail = mail
        self.openNew = (mail != None)
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')
        if not self.mail:
            self.mail = ui.current_buffer.get_email()

        def openEnvelopeFromTmpfile():
            # This parses the input from the tempfile.
            # we do this ourselves here because we want to be able to
            # just type utf-8 encoded stuff into the tempfile and let alot
            # worry about encodings.

            # get input
            f = open(tf.name)
            enc = settings.config.get('general', 'editor_writes_encoding')
            editor_input = f.read().decode(enc)
            headertext, bodytext = editor_input.split('\n\n', 1)

            # call post-edit translate hook
            translate = settings.hooks.get('post_edit_translate')
            if translate:
                bodytext = translate(bodytext, ui=ui, dbm=ui.dbman,
                                     aman=ui.accountman, log=ui.logger,
                                     config=settings.config)

            # go through multiline, utf-8 encoded headers
            key = value = None
            for line in headertext.splitlines():
                if re.match('\w+:', line):  # new k/v pair
                    if key and value:  # save old one from stack
                        del self.mail[key]  # ensure unique values in mails
                        self.mail[key] = encode_header(key, value)  # save
                    key, value = line.strip().split(':', 1)  # parse new pair
                elif key and value:  # append new line without key prefix
                    value += line
            if key and value:  # save last one if present
                del self.mail[key]
                self.mail[key] = encode_header(key, value)

            if self.mail.is_multipart():
                for part in self.mail.walk():
                    if part.get_content_maintype() == 'text':
                        if 'Content-Transfer-Encoding' in part:
                            del(part['Content-Transfer-Encoding'])
                        part.set_payload(bodytext, 'utf-8')
                        break

            f.close()
            os.unlink(tf.name)
            if self.openNew:
                ui.apply_command(EnvelopeOpenCommand(mail=self.mail))
            else:
                ui.current_buffer.set_email(self.mail)

        # decode header
        edit_headers = ['Subject', 'To', 'From']
        headertext = u''
        for key in edit_headers:
            value = u''
            if key in self.mail:
                value = decode_header(self.mail.get(key, ''))
            headertext += '%s: %s\n' % (key, value)

        if self.mail.is_multipart():
            for part in self.mail.walk():
                if part.get_content_maintype() == 'text':
                    bodytext = decode_to_unicode(part)
                    break
        else:
            bodytext = decode_to_unicode(self.mail)

        # call pre-edit translate hook
        translate = settings.hooks.get('pre_edit_translate')
        if translate:
            bodytext = translate(bodytext, ui=ui, dbm=ui.dbman,
                                 aman=ui.accountman, log=ui.logger,
                                 config=settings.config)

        #write stuff to tempfile
        tf = tempfile.NamedTemporaryFile(delete=False)
        content = '%s\n\n%s' % (headertext,
                                bodytext)
        tf.write(content.encode('utf-8'))
        tf.flush()
        tf.close()
        cmd = EditCommand(tf.name, on_success=openEnvelopeFromTmpfile,
                          refocus=False)
        ui.apply_command(cmd)


class EnvelopeSetCommand(Command):
    """sets header fields of mail open in envelope buffer"""

    def __init__(self, key='', value=u'', replace=True, **kwargs):
        self.key = key
        self.value = encode_header(key, value)
        self.replace = replace
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        envelope = ui.current_buffer
        mail = envelope.get_email()
        if self.replace:
            del(mail[self.key])
        mail[self.key] = self.value
        envelope.rebuild()


class EnvelopeSendCommand(Command):
    @defer.inlineCallbacks
    def apply(self, ui):
        envelope = ui.current_buffer
        mail = envelope.get_email()
        frm = decode_header(mail.get('From'))
        sname, saddr = email.Utils.parseaddr(frm)
        account = ui.accountman.get_account_by_address(saddr)
        if account:
            # attach signature file if present
            if account.signature:
                sig = os.path.expanduser(account.signature)
                if os.path.isfile(sig):
                    if account.signature_filename:
                        name = account.signature_filename
                    else:
                        name = None
                    helper.attach(sig, mail, filename=name)
                else:
                    ui.notify('could not locate signature: %s' % sig,
                              priority='error')
                    if (yield ui.choice('send without signature',
                                        select='yes', cancel='no')) == 'no':
                        return

            clearme = ui.notify('sending..', timeout=-1, block=False)
            reason = account.send_mail(mail)
            ui.clear_notify([clearme])
            if not reason:  # sucessfully send mail
                cmd = BufferCloseCommand(buffer=envelope)
                ui.apply_command(cmd)
                ui.notify('mail send successful')
            else:
                ui.notify('failed to send: %s' % reason, priority='error')
        else:
            ui.notify('failed to send: no account set up for %s' % saddr,
                      priority='error')


class EnvelopeAttachCommand(Command):
    def __init__(self, path=None, mail=None, **kwargs):
        Command.__init__(self, **kwargs)
        self.mail = mail
        self.path = path

    def apply(self, ui):
        msg = self.mail
        if not msg:
            msg = ui.current_buffer.get_email()

        if self.path:
            files = filter(os.path.isfile,
                           glob.glob(os.path.expanduser(self.path)))
            if not files:
                ui.notify('no matches, abort')
                return
        else:
            ui.notify('no files specified, abort')

        logging.info("attaching: %s" % files)
        for path in files:
            helper.attach(path, msg)

        if not self.mail:  # set the envelope msg iff we got it from there
            ui.current_buffer.set_email(msg)


# TAGLIST
class TaglistSelectCommand(Command):
    def apply(self, ui):
        tagstring = ui.current_buffer.get_selected_tag()
        cmd = SearchCommand(query='tag:%s' % tagstring)
        ui.apply_command(cmd)


class MoveCommand(Command):
    def __init__(self, direction, **kwargs):
        Command.__init__(self, **kwargs)
        self.direction = direction

    def apply(self, ui):
        if self.direction in ['up', 'down', 'left', 'right', 'page down']:
            ui.keypress(self.direction)


COMMANDS = {
    'search': {
        'refine': (RefineCommand, {}),
        'refineprompt': (RefinePromptCommand, {}),
        'openthread': (OpenThreadCommand, {}),
        'toggletag': (ToggleThreadTagCommand, {'tags': ['inbox']}),
        'retag': (RetagCommand, {}),
        'retagprompt': (RetagPromptCommand, {}),
    },
    'envelope': {
        'attach': (EnvelopeAttachCommand, {}),
        'send': (EnvelopeSendCommand, {}),
        'reedit': (EnvelopeEditCommand, {}),
        'subject': (EnvelopeSetCommand, {'key': 'Subject'}),
        'to': (EnvelopeSetCommand, {'key': 'To'}),
    },
    'bufferlist': {
        'closefocussed': (BufferCloseCommand, {'focussed': True}),
        'openfocussed': (BufferFocusCommand, {}),
    },
    'taglist': {
        'select': (TaglistSelectCommand, {}),
    },
    'thread': {
        'reply': (ReplyCommand, {}),
        'groupreply': (ReplyCommand, {'groupreply': True}),
        'forward': (ForwardCommand, {}),
        'fold': (FoldMessagesCommand, {'visible': False}),
        'pipeto': (PipeCommand, {}),
        'print': (PrintCommand, {}),
        'unfold': (FoldMessagesCommand, {'visible': True}),
        'select': (ThreadSelectCommand, {}),
        'save': (SaveAttachmentCommand, {}),
        'toggleheaders': (ToggleHeaderCommand, {}),
    },
    'global': {
        'move': (MoveCommand, {}),
        'bnext': (BufferFocusCommand, {'offset': 1}),
        'bprevious': (BufferFocusCommand, {'offset': -1}),
        'bufferlist': (OpenBufferlistCommand, {}),
        'bclose': (BufferCloseCommand, {}),
        'compose': (ComposeCommand, {}),
        'edit': (EditCommand, {}),
        'exit': (ExitCommand, {}),
        'flush': (FlushCommand, {}),
        'prompt': (PromptCommand, {}),
        'pyshell': (PythonShellCommand, {}),
        'refresh': (RefreshCommand, {}),
        'search': (SearchCommand, {}),
        'shellescape': (ExternalCommand, {}),
        'taglist': (TagListCommand, {}),
    }
}


def commandfactory(cmdname, mode='global', **kwargs):
    if cmdname in COMMANDS[mode]:
        (cmdclass, parms) = COMMANDS[mode][cmdname]
    elif cmdname in COMMANDS['global']:
        (cmdclass, parms) = COMMANDS['global'][cmdname]
    else:
        logging.error('there is no command %s' % cmdname)
    parms = parms.copy()
    parms.update(kwargs)
    for (key, value) in kwargs.items():
        if callable(value):
            parms[key] = value()
        else:
            parms[key] = value

    parms['prehook'] = settings.hooks.get('pre_' + cmdname)
    parms['posthook'] = settings.hooks.get('post_' + cmdname)

    logging.debug('cmd parms %s' % parms)
    return cmdclass(**parms)


def interpret_commandline(cmdline, mode):
    # TODO: use argparser here!
    if not cmdline:
        return None
    logging.debug('mode:%s got commandline "%s"' % (mode, cmdline))
    args = cmdline.split(' ', 1)
    cmd = args[0]
    if args[1:]:
        params = args[1]
    else:
        params = ''

    # unfold aliases
    if settings.config.has_option('command-aliases', cmd):
        cmd = settings.config.get('command-aliases', cmd)

    # allow to shellescape without a space after '!'
    if cmd.startswith('!'):
        params = cmd[1:] + ' ' + params
        cmd = 'shellescape'

    # check if this command makes sense in current mode
    if cmd not in COMMANDS[mode] and cmd not in COMMANDS['global']:
        logging.debug('unknown command: %s' % (cmd))
        return None

    if cmd == 'search':
        return commandfactory(cmd, mode=mode, query=params)
    if cmd == 'move':
        return commandfactory(cmd, mode=mode, direction=params)
    elif cmd == 'compose':
        h = {}
        if params:
            h = {'To': params}
        return commandfactory(cmd, mode=mode, headers=h)
    elif cmd == 'attach':
        return commandfactory(cmd, mode=mode, path=params)
    elif cmd == 'forward':
        return commandfactory(cmd, mode=mode, inline=(params == '--inline'))
    elif cmd == 'prompt':
        return commandfactory(cmd, mode=mode, startstring=params)
    elif cmd == 'refine':
        return commandfactory(cmd, mode=mode, query=params)
    elif cmd == 'retag':
        return commandfactory(cmd, mode=mode, tagsstring=params)
    elif cmd == 'subject':
        return commandfactory(cmd, mode=mode, key='Subject', value=params)
    elif cmd == 'shellescape':
        return commandfactory(cmd, mode=mode, commandstring=params)
    elif cmd == 'to':
        return commandfactory(cmd, mode=mode, key='To', value=params)
    elif cmd == 'toggletag':
        return commandfactory(cmd, mode=mode, tags=params.split())
    elif cmd == 'fold':
        return commandfactory(cmd, mode=mode, all=(params == '--all'))
    elif cmd == 'unfold':
        return commandfactory(cmd, mode=mode, all=(params == '--all'))
    elif cmd == 'save':
        args = params.split(' ')
        allset = False
        pathset = None
        if args:
            if args[0] == '--all':
                allset = True
                pathset = ' '.join(args[1:])
            else:
                pathset = params
        return commandfactory(cmd, mode=mode, all=allset, path=pathset)
    elif cmd == 'edit':
        filepath = os.path.expanduser(params)
        if os.path.isfile(filepath):
            return commandfactory(cmd, mode=mode, path=filepath)
    elif cmd == 'print':
        args = [a.strip() for a in params.split()]
        return commandfactory(cmd, mode=mode,
                              whole_thread=('--thread' in args),
                              separately=('--separately' in args))
    elif cmd == 'pipeto':
        return commandfactory(cmd, mode=mode, command=params)

    elif not params and cmd in ['exit', 'flush', 'pyshell', 'taglist',
                                'bclose', 'compose', 'openfocussed',
                                'closefocussed', 'bnext', 'bprevious', 'retag',
                                'refresh', 'bufferlist', 'refineprompt',
                                'reply', 'open', 'groupreply', 'bounce',
                                'openthread', 'toggleheaders', 'send',
                                'reedit', 'select', 'retagprompt']:
        return commandfactory(cmd, mode=mode)
    else:
        return None
