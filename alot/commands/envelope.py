import os
import re
import glob
import logging
import email
import tempfile
from twisted.internet.defer import inlineCallbacks
from twisted.internet import threads
import datetime

from alot.account import SendingMailFailed
from alot import buffers
from alot import commands
from alot.commands import Command, registerCommand
from alot import settings
from alot.commands import globals
from alot.helper import string_decode


MODE = 'envelope'


@registerCommand(MODE, 'attach', arguments=[
    (['path'], {'help':'file(s) to attach (accepts wildcads)'})])
class AttachCommand(Command):
    """attach files to the mail"""
    def __init__(self, path=None, **kwargs):
        """
        :param path: files to attach (globable string)
        :type path: str
        """
        Command.__init__(self, **kwargs)
        self.path = path

    def apply(self, ui):
        envelope = ui.current_buffer.envelope

        if self.path:  # TODO: not possible, otherwise argparse error before
            files = filter(os.path.isfile,
                           glob.glob(os.path.expanduser(self.path)))
            if not files:
                ui.notify('no matches, abort')
                return
        else:
            ui.notify('no files specified, abort')
            return

        logging.info("attaching: %s" % files)
        for path in files:
            envelope.attach(path)
        ui.current_buffer.rebuild()


@registerCommand(MODE, 'refine', arguments=[
    (['key'], {'help':'header to refine'})])
class RefineCommand(Command):
    """prompt to change the value of a header"""
    def __init__(self, key='', **kwargs):
        """
        :param key: key of the header to change
        :type key: str
        """
        Command.__init__(self, **kwargs)
        self.key = key

    def apply(self, ui):
        value = ui.current_buffer.envelope.get(self.key, '')
        cmdstring = 'set %s %s' % (self.key, value)
        ui.apply_command(globals.PromptCommand(cmdstring))


@registerCommand(MODE, 'save')
class SaveCommand(Command):
    """save draft"""
    def apply(self, ui):
        envelope = ui.current_buffer.envelope

        # determine account to use
        sname, saddr = email.Utils.parseaddr(envelope.get('From'))
        account = ui.accountman.get_account_by_address(saddr)
        if account == None:
            if not ui.accountman.get_accounts():
                ui.notify('no accounts set.', priority='error')
                return
            else:
                account = ui.accountman.get_accounts()[0]

        if account.draft_box == None:
            ui.notify('abort: account <%s> has no draft_box set.' % saddr,
                      priority='error')
            return

        mail = envelope.construct_mail()
        account.store_draft_mail(mail)
        ui.apply_command(commands.globals.BufferCloseCommand())
        ui.notify('draft saved successfully')


@registerCommand(MODE, 'send')
class SendCommand(Command):
    """send mail"""
    @inlineCallbacks
    def apply(self, ui):
        currentbuffer = ui.current_buffer  # needed to close later
        envelope = currentbuffer.envelope
        if envelope.sent_time:
            warning = 'A modified version of ' * envelope.modified_since_sent
            warning += 'this message has been sent at %s.' % envelope.sent_time
            warning += ' Do you want to resend?'
            if (yield ui.choice(warning, cancel='no',
                                msg_position='left')) == 'no':
                return
        frm = envelope.get('From')
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

        # send
        clearme = ui.notify('sending..', timeout=-1)

        def afterwards(returnvalue):
            ui.clear_notify([clearme])
            if returnvalue == 'success':  # successfully send mail
                envelope.sent_time = datetime.datetime.now()
                ui.apply_command(commands.globals.BufferCloseCommand())
                ui.notify('mail send successfully')
            else:
                ui.notify('failed to send: %s' % returnvalue,
                          priority='error')

        def thread_code():
            mail = envelope.construct_mail()
            try:
                account.send_mail(mail)
            except SendingMailFailed as e:
                return unicode(e)
            else:
                return 'success'

        d = threads.deferToThread(thread_code)
        d.addCallback(afterwards)


@registerCommand(MODE, 'edit')
class EditCommand(Command):
    """edit mail"""
    def __init__(self, envelope=None, **kwargs):
        """
        :param envelope: email to edit
        :type envelope: :class:`~alot.message.Envelope`
        """
        self.envelope = envelope
        self.openNew = (envelope != None)
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ebuffer = ui.current_buffer
        if not self.envelope:
            self.envelope = ui.current_buffer.envelope

        #determine editable headers
        edit_headers = set(settings.config.getstringlist('general',
                                                    'edit_headers_whitelist'))
        if '*' in edit_headers:
            edit_headers = set(self.envelope.headers.keys())
        blacklist = set(settings.config.getstringlist('general',
                                                  'edit_headers_blacklist'))
        if '*' in blacklist:
            blacklist = set(self.envelope.headers.keys())
        self.edit_headers = edit_headers - blacklist
        logging.info('editable headers: %s' % blacklist)

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
            translate = settings.config.get_hook('post_edit_translate')
            if translate:
                template = translate(template, ui=ui, dbm=ui.dbman,
                                    aman=ui.accountman, config=settings.config)
            self.envelope.parse_template(template)
            if self.openNew:
                ui.buffer_open(buffers.EnvelopeBuffer(ui, self.envelope))
            else:
                ebuffer.envelope = self.envelope
                ebuffer.rebuild()

        # decode header
        headertext = u''
        for key in edit_headers:
            vlist = self.envelope.get_all(key)

            # remove to be edited lines from envelope
            del self.envelope[key]

            for value in vlist:
                # newlines (with surrounding spaces) by spaces in values
                value = value.strip()
                value = re.sub('[ \t\r\f\v]*\n[ \t\r\f\v]*', ' ', value)
                headertext += '%s: %s\n' % (key, value)

        bodytext = self.envelope.body

        # call pre-edit translate hook
        translate = settings.config.get_hook('pre_edit_translate')
        if translate:
            bodytext = translate(bodytext, ui=ui, dbm=ui.dbman,
                                 aman=ui.accountman, config=settings.config)

        #write stuff to tempfile
        tf = tempfile.NamedTemporaryFile(delete=False)
        content = bodytext
        if headertext:
            content = '%s%s' % (headertext, content)
        tf.write(content.encode('utf-8'))
        tf.flush()
        tf.close()
        cmd = globals.EditCommand(tf.name, on_success=openEnvelopeFromTmpfile,
                          refocus=False)
        ui.apply_command(cmd)


@registerCommand(MODE, 'set', arguments=[
    (['--append'], {'action': 'store_true', 'help':'keep previous values'}),
    (['key'], {'help':'header to refine'}),
    (['value'], {'nargs':'+', 'help':'value'})])
class SetCommand(Command):
    """set header value"""
    def __init__(self, key, value, append=False, **kwargs):
        """
        :param key: key of the header to change
        :type key: str
        :param value: new value
        :type value: str
        """
        self.key = key
        self.value = ' '.join(value)
        self.reset = not append
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        envelope = ui.current_buffer.envelope
        if self.reset:
            if self.key in envelope:
                del(envelope[self.key])
        envelope.add(self.key, self.value)
        ui.current_buffer.rebuild()


@registerCommand(MODE, 'unset', arguments=[
    (['key'], {'help':'header to refine'})])
class UnsetCommand(Command):
    """remove header field"""
    def __init__(self, key, **kwargs):
        """
        :param key: key of the header to remove
        :type key: str
        """
        self.key = key
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        del(ui.current_buffer.envelope[self.key])
        ui.current_buffer.rebuild()


@registerCommand(MODE, 'toggleheaders')
class ToggleHeaderCommand(Command):
    """toggle display of all headers"""
    def apply(self, ui):
        ui.current_buffer.toggle_all_headers()
