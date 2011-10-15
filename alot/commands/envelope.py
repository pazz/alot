import os
import re
import glob
import logging
import email
import tempfile
from email import Charset
from twisted.internet import defer

from alot.commands import Command, registerCommand
from alot import settings
from alot import helper
from alot.message import decode_to_unicode
from alot.message import decode_header
from alot.message import encode_header
from alot.commands.globals import EditCommand
from alot.commands.globals import BufferCloseCommand
from alot.commands.globals import EnvelopeOpenCommand


MODE = 'envelope'


@registerCommand(MODE, 'attach', arguments=[
    (['path'], {'help':'file(s) to attach'})]
)
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


@registerCommand(MODE, 'refine', arguments=[
    (['key'], {'help':'header to refine'})]
)
class EnvelopeRefineCommand(Command):
    """prompt to change current value of header field"""

    def __init__(self, key='', **kwargs):
        Command.__init__(self, **kwargs)
        self.key = key

    def apply(self, ui):
        mail = ui.current_buffer.get_email()
        value = decode_header(mail.get(self.key, ''))
        ui.commandprompt('set %s %s' % (self.key, value))


@registerCommand(MODE, 'send', {})
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


@registerCommand(MODE, 'reedit', {})
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


@registerCommand(MODE, 'set', {})
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
