import os
import logging
import tempfile
from twisted.internet.defer import inlineCallbacks
import mimetypes
import shlex

from alot.commands import Command, registerCommand
from alot.commands.globals import ExternalCommand
from alot.commands.globals import FlushCommand
from alot.commands.globals import ComposeCommand
from alot import settings
from alot import widgets
from alot import completion
from alot import helper
from alot.message import decode_header
from alot.message import extract_headers
from alot.message import extract_body
from alot.message import Envelope

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
                             log=ui.logger, config=settings.config)
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
                             log=ui.logger, config=settings.config)
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


@registerCommand(MODE, 'fold', forced={'visible': False}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'fold all messages'})],
    help='fold message(s)')
@registerCommand(MODE, 'unfold', forced={'visible': True}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'unfold all messages'})],
    help='unfold message(s)')
class FoldMessagesCommand(Command):
    """fold or unfold messages"""
    def __init__(self, all=False, visible=None, **kwargs):
        """
        :param all: toggle all, not only selected message
        :type all: bool
        :param visible: unfold if `True`, fold if `False`
        :type visible: bool
        """
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


@registerCommand(MODE, 'toggleheaders')
class ToggleHeaderCommand(Command):
    """toggle display of all headers"""
    def apply(self, ui):
        try:
            msgw = ui.current_buffer.get_selection()
            msgw.toggle_full_header()
        except Exception, e:
            ui.logger.exception(e)


@registerCommand(MODE, 'pipeto', arguments=[
    (['cmd'], {'nargs':'?', 'help':'shellcommand to pipe to'}),
    (['--all'], {'action': 'store_true', 'help':'pass all messages'}),
    (['--decode'], {'action': 'store_true',
                    'help':'use only decoded body lines'}),
    (['--ids'], {'action': 'store_true',
                    'help':'only pass message ids'}),
    (['--separately'], {'action': 'store_true',
                        'help':'call command once for each message'})],
)
class PipeCommand(Command):
    """pipe message(s) to stdin of a shellcommand"""
    #TODO: use raw arg from print command here
    def __init__(self, cmd, all=False, ids=False, separately=False,
                 decode=True, noop_msg='no command specified', confirm_msg='',
                 done_msg='done', **kwargs):
        """
        :param cmd: shellcommand to open
        :type cmd: list of str
        :param all: pipe all, not only selected message
        :type all: bool
        :param ids: only write message ids, not the message source
        :type ids: bool
        :param separately: call command once per message
        :type separately: bool
        :param noop_msg: error notification to show if `cmd` is empty
        :type noop_msg: str
        :param confirm_msg: confirmation question to ask (continues directly if
                            unset)
        :type confirm_msg: str
        :param done_msg: notification message to show upon success
        :type done_msg: str
        """
        Command.__init__(self, **kwargs)
        self.cmdlist = cmd
        self.whole_thread = all
        self.separately = separately
        self.ids = ids
        self.decode = decode
        self.noop_msg = noop_msg
        self.confirm_msg = confirm_msg
        self.done_msg = done_msg

    @inlineCallbacks
    def apply(self, ui):
        # abort if command unset
        if not self.cmdlist:
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
        mailstrings = []
        if self.ids:
            mailstrings = [e.get_message_id() for e in to_print]
        else:
            mails = [m.get_email() for m in to_print]
            if self.decode:
                for mail in mails:
                    headertext = extract_headers(mail)
                    bodytext = extract_body(mail)
                    msg = '%s\n\n%s' % (headertext, bodytext)
                    mailstrings.append(msg.encode('utf-8'))
            else:
                mailstrings = [e.as_string() for e in mails]
        if not self.separately:
            mailstrings = ['\n\n'.join(mailstrings)]

        # do teh monkey
        for mail in mailstrings:
            ui.logger.debug("%s" % mail)
            out, err, retval = helper.call_cmd(self.cmdlist, stdin=mail)
            if err:
                ui.notify(err, priority='error')
                return

        # display 'done' message
        if self.done_msg:
            ui.notify(self.done_msg)


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
        :param separately: pipe raw message string to print command
        :type separately: bool
        """
        # get print command
        cmd = settings.config.get('general', 'print_cmd', fallback='')
        cmdlist = shlex.split(cmd.encode('utf-8', errors='ignore'))

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
        PipeCommand.__init__(self, cmdlist, all=all,
                             separately=separately,
                             decode=not raw,
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
        if mimetype == 'application/octet-stream' and filename:
            mt, enc = mimetypes.guess_type(filename)
            if mt:
                mimetype = mt

        handler = settings.get_mime_handler(mimetype)
        if handler:
            path = self.attachment.save(tempfile.gettempdir())
            handler = handler.replace('%s', '{}')

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
            ui.apply_command(FoldMessagesCommand())
        elif isinstance(focus, widgets.AttachmentWidget):
            logging.info('open attachment')
            ui.apply_command(OpenAttachmentCommand(focus.get_attachment()))
        else:
            logging.info('unknown widget %s' % focus)
