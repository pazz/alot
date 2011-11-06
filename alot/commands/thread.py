import os
import logging
import tempfile
from email import Charset
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.iterators import body_line_iterator
from email.iterators import typed_subpart_iterator
from twisted.internet import defer

from alot.commands import Command, registerCommand
from alot.commands.globals import ExternalCommand
from alot.commands.globals import FlushCommand
from alot.commands.globals import ComposeCommand
from alot import settings
from alot import widgets
from alot import completion
from alot import helper
from alot.message import encode_header
from alot.message import decode_header
from alot.message import extract_headers
from alot.message import extract_body

MODE = 'thread'


@registerCommand(MODE, 'reply', arguments=[
    (['--all'], {'action':'store_true', 'help':'reply to all'})],
    help='reply to currently selected message')
class ReplyCommand(Command):
    def __init__(self, message=None, all=False, **kwargs):
        """
        :param message: the original message to reply to
        :type message: `alot.message.Message`
        :param groupreply: copy other recipients from Bcc/Cc/To to the reply
        :type groupreply: boolean
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
        subject = decode_header(mail.get('Subject', ''))
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


@registerCommand(MODE, 'forward', arguments=[
    (['--attach'], {'action':'store_true', 'help':'attach original mail'})],
    help='forward currently selected message')
class ForwardCommand(Command):
    def __init__(self, message=None, attach=True, **kwargs):
        """
        :param message: the original message to forward. If None, the currently
                        selected one is used
        :type message: `alot.message.Message`
        :param attach: attach original mail instead of inline quoting its body
        :type attach: boolean
        """
        self.message = message
        self.inline = not attach
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
        subject = decode_header(mail.get('Subject', ''))
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


@registerCommand(MODE, 'fold', forced={'visible': False}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'fold all messages'})],
    help='fold message(s)')
@registerCommand(MODE, 'unfold', forced={'visible': True}, arguments=[
    (['--all'], {'action': 'store_true', 'help':'unfold all messages'})],
    help='unfold message(s)')
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


@registerCommand(MODE, 'toggleheaders',
                help='toggle display of all headers')
class ToggleHeaderCommand(Command):
    def apply(self, ui):
        msgw = ui.current_buffer.get_selection()
        msgw.toggle_full_header()


@registerCommand(MODE, 'pipeto', arguments=[
    (['cmd'], {'help':'shellcommand to pipe to'}),
    (['--all'], {'action': 'store_true', 'help':'pass all messages'}),
    (['--decode'], {'action': 'store_true',
                    'help':'use only decoded body lines'}),
    (['--ids'], {'action': 'store_true',
                    'help':'only pass message ids'}),
    (['--separately'], {'action': 'store_true',
                        'help':'call command once for each message'})],
    help='pipe message(s) to stdin of a shellcommand')
class PipeCommand(Command):
    def __init__(self, cmd, all=False, ids=False, separately=False, decode=True,
                 noop_msg='no command specified', confirm_msg='',
                 done_msg='done', **kwargs):
        Command.__init__(self, **kwargs)
        self.cmd = cmd
        self.whole_thread = all
        self.separately = separately
        self.ids = ids
        self.decode = decode
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
            out, err = helper.pipe_to_command(self.cmd, mail)
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
    help='print message(s)')
class PrintCommand(PipeCommand):
    def __init__(self, all=False, separately=False, raw=False, **kwargs):
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
        PipeCommand.__init__(self, cmd, all=all,
                             separately=separately,
                             decode=not raw,
                             noop_msg=noop_msg, confirm_msg=confirm_msg,
                             done_msg=ok_msg, **kwargs)


@registerCommand(MODE, 'save', arguments=[
    (['--all'], {'action': 'store_true', 'help':'save all attachments'}),
    (['path'], {'nargs':'?', 'help':'path to save to'})],
    help='save attachment(s)')
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
            handler = handler.replace('%s', '{}')

            def afterwards():
                os.remove(path)
            ui.apply_command(ExternalCommand(handler, path=path,
                                             on_success=afterwards,
                                             thread=True))
        else:
            ui.notify('unknown mime type')


@registerCommand(MODE, 'select')
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
