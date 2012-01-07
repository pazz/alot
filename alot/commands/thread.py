import os
import logging
import tempfile
from twisted.internet.defer import inlineCallbacks
import shlex
import re
import subprocess

from alot.commands import Command, registerCommand
from alot.commands.globals import ExternalCommand
from alot.commands.globals import FlushCommand
from alot.commands.globals import ComposeCommand
from alot.commands.globals import RefreshCommand
from alot import settings
from alot import widgets
from alot import completion
from alot import helper
from alot.message import decode_header
from alot.message import extract_headers
from alot.message import extract_body
from alot.message import Envelope
from alot.db import DatabaseROError

MODE = 'thread'


@registerCommand(MODE, 'reply', arguments=[
    (['--all'], {'action':'store_true', 'help':'reply to all'})])
class ReplyCommand(Command):
    """reply to message"""
    def __init__(self, message=None, all=False, **kwargs):
        """
        :param message: message to reply to (defaults to selected message)
        :type message: `alot.message.Message`
        :param all: group reply; copies recipients from Bcc/Cc/To to the reply
        :type all: bool
        """
        self.message = message
        self.groupreply = all
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.message:
            self.message = ui.current_buffer.get_selected_message()
        mail = self.message.get_email()
        # set body text
        name, address = self.message.get_author()
        timestamp = self.message.get_date()
        qf = settings.config.get_hook('reply_prefix')
        if qf:
            quotestring = qf(name, address, timestamp,
                             ui=ui, dbm=ui.dbman, aman=ui.accountman,
                             config=settings.config)
        else:
            quotestring = 'Quoting %s (%s)\n' % (name, timestamp)
        mailcontent = quotestring
        for line in self.message.accumulate_body().splitlines():
            mailcontent += '>' + line + '\n'

        envelope = Envelope(bodytext=mailcontent)

        # copy subject
        subject = decode_header(mail.get('Subject', ''))
        if not subject.startswith('Re:'):
            subject = 'Re: ' + subject
        envelope.add('Subject', subject)

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
            envelope.add('From', fromstring)

        # set To
        if self.groupreply:
            cleared = self.clear_my_address(my_addresses, mail.get('To', ''))
            if cleared:
                logging.info(mail['From'] + ', ' + cleared)
                to = mail['From'] + ', ' + cleared
                envelope.add('To', decode_header(to))

            else:
                envelope.add('To', decode_header(mail['From']))
            # copy cc and bcc for group-replies
            if 'Cc' in mail:
                cc = self.clear_my_address(my_addresses, mail['Cc'])
                envelope.add('Cc', decode_header(cc))
            if 'Bcc' in mail:
                bcc = self.clear_my_address(my_addresses, mail['Bcc'])
                envelope.add('Bcc', decode_header(bcc))
        else:
            envelope.add('To', decode_header(mail['From']))

        # set In-Reply-To header
        envelope.add('In-Reply-To', '<%s>' % self.message.get_message_id())

        # set References header
        old_references = mail.get('References', '')
        if old_references:
            old_references = old_references.split()
            references = old_references[-8:]
            if len(old_references) > 8:
                references = old_references[:1] + references
            references.append('<%s>' % self.message.get_message_id())
            envelope.add('References', ' '.join(references))
        else:
            envelope.add('References', '<%s>' % self.message.get_message_id())

        ui.apply_command(ComposeCommand(envelope=envelope))

    def clear_my_address(self, my_addresses, value):
        new_value = []
        for entry in value.split(','):
            if not [a for a in my_addresses if a in entry]:
                new_value.append(entry.strip())
        return ', '.join(new_value)


@registerCommand(MODE, 'forward', arguments=[
    (['--attach'], {'action':'store_true', 'help':'attach original mail'})])
class ForwardCommand(Command):
    """forward message"""
    def __init__(self, message=None, attach=True, **kwargs):
        """
        :param message: message to forward (defaults to selected message)
        :type message: `alot.message.Message`
        :param attach: attach original mail instead of inline quoting its body
        :type attach: bool
        """
        self.message = message
        self.inline = not attach
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.message:
            self.message = ui.current_buffer.get_selected_message()
        mail = self.message.get_email()

        envelope = Envelope()
        if self.inline:  # inline mode
            # set body text
            name, address = self.message.get_author()
            timestamp = self.message.get_date()
            qf = settings.config.get_hook('forward_prefix')
            if qf:
                quote = qf(name, address, timestamp,
                             ui=ui, dbm=ui.dbman, aman=ui.accountman,
                             config=settings.config)
            else:
                quote = 'Forwarded message from %s (%s):\n' % (name, timestamp)
            mailcontent = quote
            for line in self.message.accumulate_body().splitlines():
                mailcontent += '>' + line + '\n'

            envelope.body = mailcontent

        else:  # attach original mode
            # attach original msg
            mail.set_default_type('message/rfc822')
            mail['Content-Disposition'] = 'attachment'
            envelope.attachments.append(mail)

        # copy subject
        subject = decode_header(mail.get('Subject', ''))
        subject = 'Fwd: ' + subject
        envelope.add('Subject', subject)

        # set From
        # we look for own addresses in the To,Cc,Ccc headers in that order
        # and use the first match as new From header if there is one.
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
            envelope.add('From', fromstring)
        ui.apply_command(ComposeCommand(envelope=envelope))


@registerCommand(MODE, 'editnew')
class EditNewCommand(Command):
    """edit message in as new"""
    def __init__(self, message=None, **kwargs):
        """
        :param message: message to reply to (defaults to selected message)
        :type message: `alot.message.Message`
        """
        self.message = message
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if not self.message:
            self.message = ui.current_buffer.get_selected_message()
        mail = self.message.get_email()
        # set body text
        name, address = self.message.get_author()
        timestamp = self.message.get_date()
        mailcontent = self.message.accumulate_body()
        envelope = Envelope(bodytext=mailcontent)

        # copy selected headers
        to_copy = ['Subject', 'From', 'To', 'Cc', 'Bcc', 'In-Reply-To',
                   'References']
        for key in to_copy:
            value = decode_header(mail.get(key, ''))
            if value:
                envelope.add(key, value)

        # copy attachments
        for b in self.message.get_attachments():
            envelope.attach(b)

        ui.apply_command(ComposeCommand(envelope=envelope))


@registerCommand(MODE, 'fold', forced={'visible': False}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'fold all messages'})],
    help='fold message(s)')
@registerCommand(MODE, 'unfold', forced={'visible': True}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'unfold all messages'})],
    help='unfold message(s)')
@registerCommand(MODE, 'togglesource', forced={'raw': 'toggle'}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'affect all messages'})],
    help='display message source')
@registerCommand(MODE, 'toggleheaders', forced={'all_headers': 'toggle'},
    arguments=[
        (['--all'], {'action': 'store_true', 'help':'affect all messages'})],
    help='display all headers')
class ChangeDisplaymodeCommand(Command):
    """fold or unfold messages"""
    def __init__(self, all=False, visible=None, raw=None, all_headers=None,
                 **kwargs):
        """
        :param all: toggle all, not only selected message
        :type all: bool
        :param visible: unfold if `True`, fold if `False`, ignore if `None`
        :type visible: True, False, 'toggle' or None
        :param raw: display raw message text.
        :type raw: True, False, 'toggle' or None
        :param all_headers: show all headers (only visible if not in raw mode)
        :type all_headers: True, False, 'toggle' or None
        """
        self.all = all
        self.visible = visible
        self.raw = raw
        self.all_headers = all_headers
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        lines = []
        if not self.all:
            lines.append(ui.current_buffer.get_selection())
        else:
            lines = ui.current_buffer.get_message_widgets()

        for widget in lines:
            msg = widget.get_message()

            # in case the thread is yet unread, remove this tag
            if self.visible or (self.visible == 'toggle' and widget.folded):
                if 'unread' in msg.get_tags():
                    msg.remove_tags(['unread'])
                    ui.apply_command(FlushCommand())

            if self.visible == 'toggle':
                self.visible = widget.folded
            if self.raw == 'toggle':
                self.raw = not widget.show_raw
            if self.all_headers == 'toggle':
                self.all_headers = not widget.show_all_headers

            logging.debug((self.visible, self.raw, self.all_headers))
            if self.visible is not None:
                widget.folded = not self.visible
            if self.raw is not None:
                widget.show_raw = self.raw
            if self.all_headers is not None:
                widget.show_all_headers = self.all_headers
            widget.rebuild()


@registerCommand(MODE, 'pipeto', arguments=[
    (['cmd'], {'help':'shellcommand to pipe to'}),
    (['--all'], {'action': 'store_true', 'help':'pass all messages'}),
    (['--format'], {'help':'output format', 'default':'raw',
                    'choices':['raw', 'decoded', 'id', 'filepath']}),
    (['--separately'], {'action': 'store_true',
                        'help':'call command once for each message'}),
    (['--background'], {'action': 'store_true',
                        'help':'disable stdin and ignore stdout'}),
],
)
class PipeCommand(Command):
    """pipe message(s) to stdin of a shellcommand"""
    def __init__(self, cmd, all=False, separately=False,
                 background=False, format='raw',
                 noop_msg='no command specified', confirm_msg='',
                 done_msg='done', **kwargs):
        """
        :param cmd: shellcommand to open
        :type cmd: str or list of str
        :param all: pipe all, not only selected message
        :type all: bool
        :param separately: call command once per message
        :type separately: bool
        :param background: disable stdin and ignore sdtout of command
        :type background: bool
        :param format: what to pipe to the processes stdin. one of:
                       'raw': message content as is,
                       'decoded': message content, decoded quoted printable,
                       'id': message ids, separated by newlines,
                       'filepath': paths to message files on disk
        :type format: str
        :param noop_msg: error notification to show if `cmd` is empty
        :type noop_msg: str
        :param confirm_msg: confirmation question to ask (continues directly if
                            unset)
        :type confirm_msg: str
        :param done_msg: notification message to show upon success
        :type done_msg: str
        """
        Command.__init__(self, **kwargs)
        if isinstance(cmd, unicode):
            cmd = shlex.split(cmd.encode('UTF-8'))
        self.cmd = cmd
        self.whole_thread = all
        self.separately = separately
        self.background = background
        self.output_format = format
        self.noop_msg = noop_msg
        self.confirm_msg = confirm_msg
        self.done_msg = done_msg

    @inlineCallbacks
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
        pipestrings = []
        separator = '\n\n'
        logging.debug('PIPETO format')
        logging.debug(self.output_format)
        if self.output_format == 'raw':
            pipestrings = [m.get_email().as_string() for m in to_print]
        elif self.output_format == 'decoded':
            mails = [m.get_email() for m in to_print]
            for mail in mails:
                headertext = extract_headers(mail)
                bodytext = extract_body(mail)
                msg = '%s\n\n%s' % (headertext, bodytext)
                pipestrings.append(msg.encode('utf-8'))
        elif self.output_format == 'id':
            pipestrings = [e.get_message_id() for e in to_print]
            separator = '\n'
        elif self.output_format == 'filepath':
            pipestrings = [e.get_filename() for e in to_print]
            separator = '\n'

        if not self.separately:
            pipestrings = [separator.join(pipestrings)]

        # do teh monkey
        for mail in pipestrings:
            if self.background:
                logging.debug('call in background: %s' % str(self.cmd))
                proc = subprocess.Popen(self.cmd,
                                        shell=True, stdin=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                out, err = proc.communicate(mail)
            else:
                logging.debug('stop urwid screen')
                ui.mainloop.screen.stop()
                logging.debug('call: %s' % str(self.cmd))
                proc = subprocess.Popen(self.cmd, shell=True,
                                        stdin=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                out, err = proc.communicate(mail)
                logging.debug('start urwid screen')
                ui.mainloop.screen.start()
            if err:
                ui.notify(err, priority='error')
                return

        # display 'done' message
        if self.done_msg:
            ui.notify(self.done_msg)


@registerCommand(MODE, 'remove', arguments=[
    (['--all'], {'action': 'store_true', 'help':'remove whole thread'})])
class RemoveCommand(Command):
    """remove message(s) from the index"""
    def __init__(self, all=False, **kwargs):
        """
        :param all: remove all messages from thread, not just selected one
        :type all: bool
        """
        Command.__init__(self, **kwargs)
        self.all = all

    @inlineCallbacks
    def apply(self, ui):
        # get messages and notification strings
        if self.all:
            thread = ui.current_buffer.get_selected_thread()
            tid = thread.get_thread_id()
            messages = thread.get_messages().keys()
            confirm_msg = 'remove all messages in thread?'
            ok_msg = 'removed all messages in thread: %s' % tid
        else:
            msg = ui.current_buffer.get_selected_message()
            messages = [msg]
            confirm_msg = 'remove selected message?'
            ok_msg = 'removed message: %s' % msg.get_message_id()

        # ask for confirmation
        if (yield ui.choice(confirm_msg, select='yes', cancel='no')) == 'no':
            return

        # remove messages
        try:
            for m in messages:
                ui.dbman.remove_message(m)
        except DatabaseError, e:
            err_msg = str(e)
            ui.notify(err_msg, priority='error')
            logging.debug(err_msg)
            return

        # notify
        ui.notify(ok_msg)

        # refresh buffer
        ui.apply_command(RefreshCommand())


@registerCommand(MODE, 'print', arguments=[
    (['--all'], {'action': 'store_true', 'help':'print all messages'}),
    (['--raw'], {'action': 'store_true', 'help':'pass raw mail string'}),
    (['--separately'], {'action': 'store_true',
                        'help':'call print command once for each message'})],
)
class PrintCommand(PipeCommand):
    """print message(s)"""
    def __init__(self, all=False, separately=False, raw=False, **kwargs):
        """
        :param all: print all, not only selected messages
        :type all: bool
        :param separately: call print command once per message
        :type separately: bool
        :param raw: pipe raw message string to print command
        :type raw: bool
        """
        # get print command
        cmd = settings.config.get('general', 'print_cmd', fallback='')

        # set up notification strings
        if all:
            confirm_msg = 'print all messages in thread?'
            ok_msg = 'printed thread using %s' % cmd
        else:
            confirm_msg = 'print selected message?'
            ok_msg = 'printed message using %s' % cmd

        # no print cmd set
        noop_msg = 'no print command specified. Set "print_cmd" in the '\
                    'global section.'

        PipeCommand.__init__(self, cmd, all=all, separately=separately,
                             background=True,
                             format='raw' if raw else 'decoded',
                             noop_msg=noop_msg, confirm_msg=confirm_msg,
                             done_msg=ok_msg, **kwargs)


@registerCommand(MODE, 'save', arguments=[
    (['--all'], {'action': 'store_true', 'help':'save all attachments'}),
    (['path'], {'nargs':'?', 'help':'path to save to'})])
class SaveAttachmentCommand(Command):
    """save attachment(s)"""
    def __init__(self, all=False, path=None, **kwargs):
        """
        :param all: save all, not only selected attachment
        :type all: bool
        :param path: path to write to. if `all` is set, this must be a
                     directory.
        :type path: str
        """
        Command.__init__(self, **kwargs)
        self.all = all
        self.path = path

    @inlineCallbacks
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
        """
        :param attachment: attachment to open
        :type attachment: :class:`~alot.message.Attachment`
        """
        Command.__init__(self, **kwargs)
        self.attachment = attachment

    def apply(self, ui):
        logging.info('open attachment')
        mimetype = self.attachment.get_content_type()
        filename = self.attachment.get_filename()

        handler = settings.get_mime_handler(mimetype)
        if handler:
            path = self.attachment.save(tempfile.gettempdir())
            handler = re.sub('\'?%s\'?', '{}', handler)

            # 'needsterminal' makes handler overtake the terminal
            nt = settings.get_mime_handler(mimetype, key='needsterminal')
            overtakes = (nt is None)

            def afterwards():
                os.remove(path)

            ui.apply_command(ExternalCommand(handler, path=path,
                                             on_success=afterwards,
                                             thread=overtakes))
        else:
            ui.notify('unknown mime type')


@registerCommand(MODE, 'select')
class ThreadSelectCommand(Command):
    """select focussed element. The fired action depends on the focus:
        - if message summary, this toggles visibility of the message,
        - if attachment line, this opens the attachment"""
    def apply(self, ui):
        focus = ui.get_deep_focus()
        if isinstance(focus, widgets.MessageSummaryWidget):
            ui.apply_command(ChangeDisplaymodeCommand(visible='toggle'))
        elif isinstance(focus, widgets.AttachmentWidget):
            logging.info('open attachment')
            ui.apply_command(OpenAttachmentCommand(focus.get_attachment()))
        else:
            logging.info('unknown widget %s' % focus)


@registerCommand(MODE, 'tag', forced={'action': 'add'}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'tag all messages in thread'}),
    (['tags'], {'help':'comma separated list of tags'})])
@registerCommand(MODE, 'untag', forced={'action': 'remove'}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'tag all messages in thread'}),
    (['tags'], {'help':'comma separated list of tags'})])
@registerCommand(MODE, 'toggletags', forced={'action': 'toggle'}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'tag all messages in thread'}),
    (['tags'], {'help':'comma separated list of tags'})])
class TagCommand(Command):
    """manipulate message tags"""
    def __init__(self, tags=u'', action='add', all=False, **kwargs):
        """
        :param tags: comma separated list of tagstrings to set
        :type tags: str
        :param all: tag all messages in thread
        :type all: bool
        :param action: adds tags if 'add', removes them if 'remove' or toggle
                       individually if 'toggle'
        :type action: str
        """
        self.tagsstring = tags
        self.all = all
        self.action = action
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        if self.all:
            mwidgets = ui.current_buffer.get_messagewidgets()
        else:
            mwidgets = [ui.current_buffer.get_selection()]
        messages = [mw.get_message() for mw in mwidgets]
        logging.debug('TAG %s' % str(messages))

        tags = filter(lambda x: x, self.tagsstring.split(','))
        try:
            for m in messages:
                if self.action == 'add':
                    m.add_tags(tags)
                elif self.action == 'remove':
                    m.remove_tags(tags)
                elif self.action == 'toggle':
                    to_remove = []
                    to_add = []
                    for t in tags:
                        if t in m.get_tags():
                            to_remove.append(t)
                        else:
                            to_add.append(t)
                    m.remove_tags(to_remove)
                    m.add_tags(to_add)
        except DatabaseROError:
            ui.notify('index in read-only mode', priority='error')
            return

        # flush index
        ui.apply_command(FlushCommand())

        # TODO: refresh widgets
        for mw in mwidgets:
            mw.rebuild()
