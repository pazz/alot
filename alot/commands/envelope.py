import os
import re
import glob
import logging
import email
import tempfile
from email import Charset
from twisted.internet import defer
import threading

from alot.commands import Command, registerCommand
from alot import settings
from alot import helper
from alot.message import decode_header
from alot.message import encode_header
from alot.message import extract_headers
from alot.message import extract_body
from alot.commands.globals import EditCommand
from alot.commands.globals import BufferCloseCommand
from alot.commands.globals import EnvelopeOpenCommand
from alot.helper import string_decode


MODE = 'envelope'


@registerCommand(MODE, 'attach', help='attach files to the mail', arguments=[
    (['path'], {'help':'file(s) to attach (accepts wildcads)'})])
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
            msg = helper.attach(path, msg)
        ui.current_buffer.set_email(msg)


@registerCommand(MODE, 'refine', help='prompt to change the value of a header',
                 arguments=[
    (['key'], {'help':'header to refine'})])
class EnvelopeRefineCommand(Command):
    def __init__(self, key='', **kwargs):
        Command.__init__(self, **kwargs)
        self.key = key

    def apply(self, ui):
        mail = ui.current_buffer.get_email()
        value = decode_header(mail.get(self.key, ''))
        ui.commandprompt('set %s %s' % (self.key, value))


@registerCommand(MODE, 'send', help='sends mail')
class EnvelopeSendCommand(Command):
    @defer.inlineCallbacks
    def apply(self, ui):
        envelope = ui.current_buffer  # needed to close later
        mail = envelope.get_email()
        frm = decode_header(mail.get('From'))
        sname, saddr = email.Utils.parseaddr(frm)
        omit_signature = False

        # determine account to use for sending
        account = ui.accountman.get_account_by_address(saddr)
        if account == None:
            if not ui.accountman.get_accounts():
                ui.notify('no accounts set', priority='error')
                return
            else:
                account = ui.accountman.get_accounts()[0]
                omit_signature = True

        # attach signature file if present
        if account.signature and not omit_signature:
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

        # send
        clearme = ui.notify('sending..', timeout=-1)

        def afterwards(returnvalue):
            ui.clear_notify([clearme])
            if returnvalue == 'success':  # sucessfully send mail
                cmd = BufferCloseCommand(buffer=envelope)
                ui.apply_command(cmd)
                ui.notify('mail send successful')
            else:
                ui.notify('failed to send: %s' % returnvalue,
                          priority='error')

        write_fd = ui.mainloop.watch_pipe(afterwards)

        def thread_code():
            os.write(write_fd, account.send_mail(mail) or 'success')

        thread = threading.Thread(target=thread_code)
        thread.start()


@registerCommand(MODE, 'edit', help='edit currently open mail')
class EnvelopeEditCommand(Command):
    def __init__(self, mail=None, **kwargs):
        self.mail = mail
        self.openNew = (mail != None)
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')
        if not self.mail:
            self.mail = ui.current_buffer.get_email()

        #determine editable headers
        edit_headers = set(settings.config.getstringlist('general',
                                                    'edit_headers_whitelist'))
        if '*' in edit_headers:
            edit_headers = set(self.mail.keys())
        blacklist = set(settings.config.getstringlist('general',
                                                  'edit_headers_blacklist'))
        if '*' in blacklist:
            blacklist = set(self.mail.keys())
        ui.logger.debug('BLACKLIST: %s' % blacklist)
        self.edit_headers = edit_headers - blacklist
        ui.logger.info('editable headers: %s' % blacklist)

        def openEnvelopeFromTmpfile():
            # This parses the input from the tempfile.
            # we do this ourselves here because we want to be able to
            # just type utf-8 encoded stuff into the tempfile and let alot
            # worry about encodings.

            # get input
            f = open(tf.name)
            enc = settings.config.get('general', 'editor_writes_encoding')
            editor_input = string_decode(f.read(), enc)
            if self.edit_headers:
                headertext, bodytext = editor_input.split('\n\n', 1)
            else:
                headertext = ''
                bodytext = editor_input

            # call post-edit translate hook
            translate = settings.hooks.get('post_edit_translate')
            if translate:
                bodytext = translate(bodytext, ui=ui, dbm=ui.dbman,
                                     aman=ui.accountman, log=ui.logger,
                                     config=settings.config)

            # go through multiline, utf-8 encoded headers
            # we decode the edited text ourselves here as
            # email.message_from_file can't deal with raw utf8 header values
            key = value = None
            for line in headertext.splitlines():
                if re.match('[a-zA-Z0-9_-]+:', line):  # new k/v pair
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
        headertext = extract_headers(self.mail, self.edit_headers)

        bodytext = extract_body(self.mail)

        # call pre-edit translate hook
        translate = settings.hooks.get('pre_edit_translate')
        if translate:
            bodytext = translate(bodytext, ui=ui, dbm=ui.dbman,
                                 aman=ui.accountman, log=ui.logger,
                                 config=settings.config)

        #write stuff to tempfile
        tf = tempfile.NamedTemporaryFile(delete=False)
        content = bodytext
        if headertext:
            content = '%s\n\n%s' % (headertext, content)
        tf.write(content.encode('utf-8'))
        tf.flush()
        tf.close()
        cmd = EditCommand(tf.name, on_success=openEnvelopeFromTmpfile,
                          refocus=False)
        ui.apply_command(cmd)


@registerCommand(MODE, 'set', help='set header value', arguments=[
    (['--append'], {'action': 'store_true', 'help':'keep previous value'}),
    (['key'], {'help':'header to refine'}),
    (['value'], {'nargs':'+', 'help':'value'})])
class EnvelopeSetCommand(Command):
    def __init__(self, key, value, append=False, **kwargs):
        self.key = key
        self.value = encode_header(key, ' '.join(value))
        self.append = append
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        envelope = ui.current_buffer
        mail = envelope.get_email()
        if not self.append:
            del(mail[self.key])
        mail[self.key] = self.value
        envelope.set_email(mail)
        envelope.rebuild()


@registerCommand(MODE, 'unset', help='remove header field', arguments=[
    (['key'], {'help':'header to refine'})])
class EnvelopeSetCommand(Command):
    def __init__(self, key, **kwargs):
        self.key = key
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        mail = ui.current_buffer.get_email()
        del(mail[self.key])
        ui.current_buffer.set_email(mail)


@registerCommand(MODE, 'toggleheaders',
                help='toggle display of all headers')
class ToggleHeaderCommand(Command):
    def apply(self, ui):
        ui.current_buffer.header_wgt.toggle_all()
