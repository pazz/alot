import argparse
import os
import re
import glob
import logging
import email
import tempfile
from twisted.internet.defer import inlineCallbacks
import datetime

from alot.account import SendingMailFailed
from alot.errors import GPGProblem
from alot import buffers
from alot import commands
from alot import crypto
from alot.commands import Command, registerCommand
from alot.commands import globals
from alot.helper import string_decode
from alot.settings import settings


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
        account = settings.get_account_by_address(saddr)
        if account == None:
            if not settings.get_accounts():
                ui.notify('no accounts set.', priority='error')
                return
            else:
                account = settings.get_accounts()[0]

        if account.draft_box == None:
            ui.notify('abort: account <%s> has no draft_box set.' % saddr,
                      priority='error')
            return

        mail = envelope.construct_mail()
        # store mail locally
        # add Date header
        mail['Date'] = email.Utils.formatdate(localtime=True)
        path = account.store_draft_mail(mail)
        ui.notify('draft saved successfully')

        # add mail to index if maildir path available
        if path is not None:
            logging.debug('adding new mail to index')
            ui.dbman.add_message(path, account.draft_tags)
            ui.apply_command(globals.FlushCommand())
        ui.apply_command(commands.globals.BufferCloseCommand())


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

        # determine account to use for sending
        account = settings.get_account_by_address(saddr)
        if account == None:
            if not settings.get_accounts():
                ui.notify('no accounts set', priority='error')
                return
            else:
                account = settings.get_accounts()[0]

        clearme = ui.notify(u'constructing mail (GPG, attachments)\u2026',
                            timeout=-1)

        try:
            mail = envelope.construct_mail()
        except GPGProblem, e:
            ui.clear_notify([clearme])
            ui.notify(e.message, priority='error')
            return

        ui.clear_notify([clearme])

        # send
        clearme = ui.notify('sending..', timeout=-1)

        def afterwards(returnvalue):
            logging.debug('mail sent successfully')
            ui.clear_notify([clearme])
            envelope.sent_time = datetime.datetime.now()
            ui.apply_command(commands.globals.BufferCloseCommand())
            ui.notify('mail sent successfully')
            # store mail locally
            # add Date header
            if 'Date' not in mail:
                mail['Date'] = email.Utils.formatdate(localtime=True)
            path = account.store_sent_mail(mail)
            # add mail to index if maildir path available
            if path is not None:
                logging.debug('adding new mail to index')
                ui.dbman.add_message(path, account.sent_tags)
                ui.apply_command(globals.FlushCommand())

        def errb(failure):
            ui.clear_notify([clearme])
            failure.trap(SendingMailFailed)
            errmsg = 'failed to send: %s' % failure.value
            ui.notify(errmsg, priority='error')

        d = account.send_mail(mail)
        d.addCallback(afterwards)
        d.addErrback(errb)
        logging.debug('added errbacks,callbacks')


@registerCommand(MODE, 'edit', arguments=[
    (['--spawn'], {'action': 'store_true',
                   'help':'force spawning of editor in a new terminal'}),
    (['--no-refocus'], {'action': 'store_false', 'dest':'refocus',
                        'help':'don\'t refocus envelope after editing'}),
    ])
class EditCommand(Command):
    """edit mail"""
    def __init__(self, envelope=None, spawn=None, refocus=True, **kwargs):
        """
        :param envelope: email to edit
        :type envelope: :class:`~alot.db.envelope.Envelope`
        :param spawn: force spawning of editor in a new terminal
        :type spawn: bool
        :param refocus: m
        """
        self.envelope = envelope
        self.openNew = (envelope != None)
        self.force_spawn = spawn
        self.refocus = refocus
        self.edit_only_body = False
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ebuffer = ui.current_buffer
        if not self.envelope:
            self.envelope = ui.current_buffer.envelope

        #determine editable headers
        edit_headers = set(settings.get('edit_headers_whitelist'))
        if '*' in edit_headers:
            edit_headers = set(self.envelope.headers.keys())
        blacklist = set(settings.get('edit_headers_blacklist'))
        if '*' in blacklist:
            blacklist = set(self.envelope.headers.keys())
        edit_headers = edit_headers - blacklist
        logging.info('editable headers: %s' % edit_headers)

        def openEnvelopeFromTmpfile():
            # This parses the input from the tempfile.
            # we do this ourselves here because we want to be able to
            # just type utf-8 encoded stuff into the tempfile and let alot
            # worry about encodings.

            # get input
            f = open(tf.name)
            os.unlink(tf.name)
            enc = settings.get('editor_writes_encoding')
            template = string_decode(f.read(), enc)
            f.close()

            # call post-edit translate hook
            translate = settings.get_hook('post_edit_translate')
            if translate:
                template = translate(template, ui=ui, dbm=ui.dbman)
            self.envelope.parse_template(template,
                                         only_body=self.edit_only_body)
            if self.openNew:
                ui.buffer_open(buffers.EnvelopeBuffer(ui, self.envelope))
            else:
                ebuffer.envelope = self.envelope
                ebuffer.rebuild()

        # decode header
        headertext = u''
        for key in edit_headers:
            vlist = self.envelope.get_all(key)
            if not vlist:
                # ensure editable headers are present in template
                vlist = ['']
            else:
                # remove to be edited lines from envelope
                del self.envelope[key]

            for value in vlist:
                # newlines (with surrounding spaces) by spaces in values
                value = value.strip()
                value = re.sub('[ \t\r\f\v]*\n[ \t\r\f\v]*', ' ', value)
                headertext += '%s: %s\n' % (key, value)

        # determine editable content
        bodytext = self.envelope.body
        if headertext:
            content = '%s\n%s' % (headertext, bodytext)
            self.edit_only_body = False
        else:
            content = bodytext
            self.edit_only_body = True

        # call pre-edit translate hook
        translate = settings.get_hook('pre_edit_translate')
        if translate:
            content = translate(content, ui=ui, dbm=ui.dbman)

        #write stuff to tempfile
        tf = tempfile.NamedTemporaryFile(delete=False, prefix='alot.')
        tf.write(content.encode('utf-8'))
        tf.flush()
        tf.close()
        cmd = globals.EditCommand(tf.name, on_success=openEnvelopeFromTmpfile,
                          spawn=self.force_spawn, thread=self.force_spawn,
                          refocus=self.refocus)
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


@registerCommand(MODE, 'sign', forced={'action': 'sign'}, arguments=[
    (['keyid'], {'nargs':argparse.REMAINDER, 'help':'which key id to use'})],
    help='mark mail to be signed before sending')
@registerCommand(MODE, 'unsign', forced={'action': 'unsign'},
    help='mark mail not to be signed before sending')
@registerCommand(MODE, 'togglesign', forced={'action': 'toggle'}, arguments=[
    (['keyid'], {'nargs':argparse.REMAINDER, 'help':'which key id to use'})],
    help='toggle sign status')
class SignCommand(Command):
    """toggle signing this email"""
    def __init__(self, action=None, keyid=None, **kwargs):
        """
        :param action: whether to sign/unsign/toggle
        :type action: str
        :param keyid: which key id to use
        :type keyid: str
        """
        self.action = action
        self.keyid = keyid
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        sign = None
        key = None
        envelope = ui.current_buffer.envelope
        # sign status
        if self.action == 'sign':
            sign = True
        elif self.action == 'unsign':
            sign = False
        elif self.action == 'toggle':
            sign = not envelope.sign
        envelope.sign = sign

        # try to find key if hint given as parameter
        if sign:
            if len(self.keyid) > 0:
                keyid = str(' '.join(self.keyid))
                try:
                    key = crypto.CryptoContext().get_key(keyid)
                except GPGProblem, e:
                    envelope.sign = False
                    ui.notify(e.message, priority='error')
                    return
                envelope.sign_key = key

        # reload buffer
        ui.current_buffer.rebuild()
