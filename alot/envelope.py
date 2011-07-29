"""
This file is part of alot.

Alot is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

Notmuch is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License
along with notmuch.  If not, see <http://www.gnu.org/licenses/>.

Copyright (C) 2011 Patrick Totzke <patricktotzke@gmail.com>
"""
import urwid
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email import Charset
import os
import email

import widgets
import buffer
import command
import settings
from message import decode_to_unicode
from message import decode_header
from message import encode_header


class EnvelopeBuffer(buffer.Buffer):
    def __init__(self, ui, email):
        self.ui = ui
        self.email = email
        self.rebuild()
        buffer.Buffer.__init__(self, ui, self.body, 'envelope')
        self.autoparms = {'email': self.get_email}

    def __str__(self):
        return "to: %s" % decode_header(self.email['To'])

    def get_email(self):
        return self.email

    def set_email(self, mail):
        self.email = mail
        self.rebuild()

    def rebuild(self):
        displayed_widgets = []
        dh = settings.config.getstringlist('general', 'displayed_headers')
        self.header_wgt = widgets.MessageHeaderWidget(self.email,
                                                      displayed_headers=dh)
        displayed_widgets.append(self.header_wgt)
        self.body_wgt = widgets.MessageBodyWidget(self.email)
        displayed_widgets.append(self.body_wgt)
        self.body = urwid.ListBox(displayed_widgets)


class EnvelopeEditCommand(command.Command):
    """re-edits mail in from envelope buffer"""
    def __init__(self, mail=None, **kwargs):
        self.mail = mail
        self.openNew = (mail != None)
        command.Command.__init__(self, **kwargs)

    def apply(self, ui):
        Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')
        if not self.mail:
            self.mail = ui.current_buffer.get_email()

        def openEnvelopeFromTmpfile():
            f = open(tf.name)
            editor_input = f.read().decode('utf-8')

            #split editor out
            headertext, bodytext = editor_input.split('\n\n', 1)

            for line in headertext.splitlines():
                key, value = line.strip().split(':', 1)
                value = value.strip()
                del self.mail[key]  # ensure there is only one
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
                ui.apply_command(command.OpenEnvelopeCommand(email=self.mail))
            else:
                ui.current_buffer.set_email(self.mail)

        # decode header
        edit_headers = ['Subject', 'To', 'From']
        headertext = u''
        for key in edit_headers:
            value = u''
            if key in self.mail:
                value = decode_header(self.mail[key])
            headertext += '%s: %s\n' % (key, value)

        if self.mail.is_multipart():
            for part in self.mail.walk():
                if part.get_content_maintype() == 'text':
                    bodytext = decode_to_unicode(part)
                    break
        else:
            bodytext = decode_to_unicode(self.mail)

        #write stuff to tempfile
        tf = tempfile.NamedTemporaryFile(delete=False)
        content = '%s\n\n%s' % (headertext,
                                bodytext)
        tf.write(content.encode('utf-8'))
        tf.flush()
        tf.close()
        cmd = command.EditCommand(tf.name, on_success=openEnvelopeFromTmpfile,
                                  refocus=False)
        ui.apply_command(cmd)


class EnvelopeSetCommand(command.Command):
    """sets header fields of mail open in envelope buffer"""

    def __init__(self, key='', value=u'', replace=True, **kwargs):
        self.key = key
        self.value = encode_header(key, value)
        self.replace = replace
        command.Command.__init__(self, **kwargs)

    def apply(self, ui):
        envelope = ui.current_buffer
        mail = envelope.get_email()
        if self.replace:
            del(mail[self.key])
        mail[self.key] = self.value
        envelope.rebuild()


class SendMailCommand(command.Command):
    def apply(self, ui):
        envelope = ui.current_buffer
        mail = envelope.get_email()
        frm = decode_header(mail.get('From'))
        sname, saddr = email.Utils.parseaddr(frm)
        account = ui.accountman.get_account_by_address(saddr)
        if account:
            success, reason = account.sender.send_mail(mail)
            if success:
                cmd = command.BufferCloseCommand(buffer=envelope)
                ui.apply_command(cmd)
                ui.notify('mail send successful')
            else:
                ui.notify('failed to send: %s' % reason)
        else:
            ui.notify('failed to send: no account set up for %s' % saddr)
