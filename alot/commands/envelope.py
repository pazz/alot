import os
import re
import glob
import logging
import email
import tempfile
from email import Charset
from email.iterators import typed_subpart_iterator
from twisted.internet import defer
import threading

from alot import buffers
from alot.commands import Command, registerCommand
from alot import settings
from alot import helper
from alot.message import decode_header
from alot.message import encode_header
from alot.message import extract_headers
from alot.message import DisensembledMail
from alot.message import extract_body
from alot.commands.globals import EditCommand
from alot.commands.globals import BufferCloseCommand
from alot.commands.globals import EnvelopeOpenCommand
from alot.helper import string_decode


MODE = 'envelope'


@registerCommand(MODE, 'attach', help='attach files to the mail', arguments=[
    (['path'], {'help':'file(s) to attach (accepts wildcads)'})])
class EnvelopeAttachCommand(Command):
    def __init__(self, path=None, **kwargs):
        Command.__init__(self, **kwargs)
        self.path = path

    def apply(self, ui):
        msg = ui.current_buffer.dmail

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
            msg.attachments.append(helper.mimewrap(path))
        ui.current_buffer.rebuild()


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
                mail.attach(helper.mimewrap(sig, filename=name))
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
        envelope = ui.current_buffer
        if not self.mail:
            self.mail = ui.current_buffer.dmail

        #determine editable headers
        edit_headers = set(settings.config.getstringlist('general',
                                                    'edit_headers_whitelist'))
        if '*' in edit_headers:
            edit_headers = set(self.mail.headers.keys())
        blacklist = set(settings.config.getstringlist('general',
                                                  'edit_headers_blacklist'))
        if '*' in blacklist:
            blacklist = set(self.mail.headers.keys())
        self.edit_headers = edit_headers - blacklist
        ui.logger.info('editable headers: %s' % blacklist)

        def openEnvelopeFromTmpfile():
            # This parses the input from the tempfile.
            # we do this ourselves here because we want to be able to
            # just type utf-8 encoded stuff into the tempfile and let alot
            # worry about encodings.

            # get input
            f = open(tf.name)
            os.unlink(tf.name)
            enc = settings.config.get('general', 'editor_writes_encoding')
            template = string_decode(f.read(), enc)
            f.close()

            # call post-edit translate hook
            translate = settings.hooks.get('post_edit_translate')
            if translate:
                template = translate(template, ui=ui, dbm=ui.dbman,
                                     aman=ui.accountman, log=ui.logger,
                                     config=settings.config)
            self.mail.parse_template(template)
            if self.openNew:
                ui.buffer_open(buffers.EnvelopeBuffer(ui, dmail=self.mail))
            else:
                envelope.dmail = self.mail
                envelope.rebuild()

        # decode header
        headertext = u''
        for key in edit_headers:
            value = decode_header(self.mail.headers.get(key, ''))
            headertext += '%s: %s\n' % (key, value)

        bodytext = self.mail.body

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
            content = '%s%s' % (headertext, content)
        tf.write(content.encode('utf-8'))
        tf.flush()
        tf.close()
        cmd = EditCommand(tf.name, on_success=openEnvelopeFromTmpfile,
                          refocus=False)
        ui.apply_command(cmd)
        #except Exception, e:
        #    ui.logger.exception(e)


@registerCommand(MODE, 'set', help='set header value', arguments=[
    #(['--append'], {'action': 'store_true', 'help':'keep previous value'}),
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
        envelope.dmail.headers[self.key] = self.value
        envelope.rebuild()


@registerCommand(MODE, 'unset', help='remove header field', arguments=[
    (['key'], {'help':'header to refine'})])
class EnvelopeSetCommand(Command):
    def __init__(self, key, **kwargs):
        self.key = key
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        envelope = ui.current_buffer
        dmail = envelope.dmail
        del(dmail.headers[self.key])
        envelope.rebuild()


@registerCommand(MODE, 'toggleheaders',
                help='toggle display of all headers')
class ToggleHeaderCommand(Command):
    def apply(self, ui):
        ui.current_buffer.header_wgt.toggle_all()
