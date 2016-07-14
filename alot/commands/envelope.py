# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse
import os
import re
import glob
import logging
import email
import tempfile
from twisted.internet.defer import inlineCallbacks
import datetime

from alot.account import SendingMailFailed, StoreMailError
from alot.errors import GPGProblem
from alot import buffers
from alot import commands
from alot import crypto
from alot.commands import Command, registerCommand
from alot.commands import globals
from alot.commands.utils import get_keys
from alot.helper import string_decode
from alot.helper import email_as_string
from alot.settings import settings
from alot.utils.booleanaction import BooleanAction
from alot.db.errors import DatabaseError


MODE = 'envelope'


@registerCommand(MODE, 'attach', arguments=[
    (['path'], {'help': 'file(s) to attach (accepts wildcads)'})])
class AttachCommand(Command):
    """attach files to the mail"""
    repeatable = True

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


@registerCommand(MODE, 'unattach', arguments=[
    (['hint'], {'nargs': '?', 'help': 'which attached file to remove'}),
])
class UnattachCommand(Command):
    """remove attachments from current envelope"""
    repeatable = True

    def __init__(self, hint=None, **kwargs):
        """
        :param hint: which attached file to remove
        :type hint: str
        """
        Command.__init__(self, **kwargs)
        self.hint = hint

    def apply(self, ui):
        envelope = ui.current_buffer.envelope

        if self.hint is not None:
            for a in envelope.attachments:
                if self.hint in a.get_filename():
                    envelope.attachments.remove(a)
        else:
            envelope.attachments = []
        ui.current_buffer.rebuild()


@registerCommand(MODE, 'refine', arguments=[
    (['key'], {'help': 'header to refine'})])
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
        if account is None:
            if not settings.get_accounts():
                ui.notify('no accounts set.', priority='error')
                return
            else:
                account = settings.get_accounts()[0]

        if account.draft_box is None:
            ui.notify('abort: account <%s> has no draft_box set.' % saddr,
                      priority='error')
            return

        mail = envelope.construct_mail()
        # store mail locally
        # add Date header
        mail['Date'] = email.Utils.formatdate(localtime=True)
        path = account.store_draft_mail(email_as_string(mail))

        msg = 'draft saved successfully'

        # add mail to index if maildir path available
        if path is not None:
            ui.notify(msg + ' to %s' % path)
            logging.debug('adding new mail to index')
            try:
                ui.dbman.add_message(path, account.draft_tags)
                ui.apply_command(globals.FlushCommand())
                ui.apply_command(commands.globals.BufferCloseCommand())
            except DatabaseError as e:
                logging.error(e.message)
                ui.notify('could not index message:\n%s' % e.message,
                          priority='error',
                          block=True)
        else:
            ui.apply_command(commands.globals.BufferCloseCommand())


@registerCommand(MODE, 'send')
class SendCommand(Command):
    """send mail"""
    def __init__(self, mail=None, envelope=None, **kwargs):
        """
        :param mail: email to send
        :type email: email.message.Message
        :param envelope: envelope to use to construct the outgoing mail. This
                         will be ignored in case the mail parameter is set.
        :type envelope: alot.db.envelope.envelope
        """
        Command.__init__(self, **kwargs)
        self.mail = mail
        self.envelope = envelope
        self.envelope_buffer = None

    @inlineCallbacks
    def apply(self, ui):
        if self.mail is None:
            if self.envelope is None:
                # needed to close later
                self.envelope_buffer = ui.current_buffer
                self.envelope = self.envelope_buffer.envelope

            # This is to warn the user before re-sending
            # an already sent message in case the envelope buffer
            # was not closed because it was the last remaining buffer.
            if self.envelope.sent_time:
                mod = self.envelope.modified_since_sent
                when = self.envelope.sent_time
                warning = 'A modified version of ' * mod
                warning += 'this message has been sent at %s.' % when
                warning += ' Do you want to resend?'
                if (yield ui.choice(warning, cancel='no',
                                    msg_position='left')) == 'no':
                    return

            # don't do anything if another SendCommand is in the middle of
            # sending the message and we were triggered accidentally
            if self.envelope.sending:
                msg = 'sending this message already!'
                logging.debug(msg)
                return

            clearme = ui.notify(u'constructing mail (GPG, attachments)\u2026',
                                timeout=-1)

            try:
                self.mail = self.envelope.construct_mail()
                self.mail['Date'] = email.Utils.formatdate(localtime=True)
                self.mail = email_as_string(self.mail)
            except GPGProblem, e:
                ui.clear_notify([clearme])
                ui.notify(e.message, priority='error')
                return

            ui.clear_notify([clearme])

        # determine account to use for sending
        msg = self.mail
        if not isinstance(msg, email.message.Message):
            msg = email.message_from_string(self.mail)
        sname, saddr = email.Utils.parseaddr(msg.get('From', ''))
        account = settings.get_account_by_address(saddr)
        if account is None:
            if not settings.get_accounts():
                ui.notify('no accounts set', priority='error')
                return
            else:
                account = settings.get_accounts()[0]

        # make sure self.mail is a string
        logging.debug(self.mail.__class__)
        if isinstance(self.mail, email.message.Message):
            self.mail = str(self.mail)

        # define callback
        def afterwards(returnvalue):
            initial_tags = []
            if self.envelope is not None:
                self.envelope.sending = False
                self.envelope.sent_time = datetime.datetime.now()
                initial_tags = self.envelope.tags
            logging.debug('mail sent successfully')
            ui.clear_notify([clearme])
            if self.envelope_buffer is not None:
                cmd = commands.globals.BufferCloseCommand(self.envelope_buffer)
                ui.apply_command(cmd)
            ui.notify('mail sent successfully')

            # store mail locally
            # This can raise StoreMailError
            path = account.store_sent_mail(self.mail)

            # add mail to index if maildir path available
            if path is not None:
                logging.debug('adding new mail to index')
                ui.dbman.add_message(path, account.sent_tags + initial_tags)
                ui.apply_command(globals.FlushCommand())

        # define errback
        def send_errb(failure):
            if self.envelope is not None:
                self.envelope.sending = False
            ui.clear_notify([clearme])
            failure.trap(SendingMailFailed)
            logging.error(failure.getTraceback())
            errmsg = 'failed to send: %s' % failure.value
            ui.notify(errmsg, priority='error', block=True)

        def store_errb(failure):
            failure.trap(StoreMailError)
            logging.error(failure.getTraceback())
            errmsg = 'could not store mail: %s' % failure.value
            ui.notify(errmsg, priority='error', block=True)

        # send out
        clearme = ui.notify('sending..', timeout=-1)
        if self.envelope is not None:
            self.envelope.sending = True
        d = account.send_mail(self.mail)
        d.addCallback(afterwards)
        d.addErrback(send_errb)
        d.addErrback(store_errb)


@registerCommand(MODE, 'edit', arguments=[
    (['--spawn'], {'action': BooleanAction, 'default': None,
                   'help': 'spawn editor in new terminal'}),
    (['--refocus'], {'action': BooleanAction, 'default': True,
                     'help': 'refocus envelope after editing'})])
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
        self.openNew = (envelope is not None)
        self.force_spawn = spawn
        self.refocus = refocus
        self.edit_only_body = False
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ebuffer = ui.current_buffer
        if not self.envelope:
            self.envelope = ui.current_buffer.envelope

        # determine editable headers
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
            # tempfile will be removed on buffer cleanup
            f = open(self.envelope.tmpfile.name)
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

        # write stuff to tempfile
        old_tmpfile = None
        if self.envelope.tmpfile:
            old_tmpfile = self.envelope.tmpfile
        self.envelope.tmpfile = tempfile.NamedTemporaryFile(delete=False,
                                                            prefix='alot.',
                                                            suffix='.eml')
        self.envelope.tmpfile.write(content.encode('utf-8'))
        self.envelope.tmpfile.flush()
        self.envelope.tmpfile.close()
        if old_tmpfile:
            os.unlink(old_tmpfile.name)
        cmd = globals.EditCommand(self.envelope.tmpfile.name,
                                  on_success=openEnvelopeFromTmpfile,
                                  spawn=self.force_spawn,
                                  thread=self.force_spawn,
                                  refocus=self.refocus)
        ui.apply_command(cmd)


@registerCommand(MODE, 'set', arguments=[
    (['--append'], {'action': 'store_true', 'help': 'keep previous values'}),
    (['key'], {'help': 'header to refine'}),
    (['value'], {'nargs': '+', 'help': 'value'})])
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
                del envelope[self.key]
        envelope.add(self.key, self.value)
        ui.current_buffer.rebuild()


@registerCommand(MODE, 'unset', arguments=[
    (['key'], {'help': 'header to refine'})])
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
        del ui.current_buffer.envelope[self.key]
        ui.current_buffer.rebuild()


@registerCommand(MODE, 'toggleheaders')
class ToggleHeaderCommand(Command):
    """toggle display of all headers"""
    repeatable = True

    def apply(self, ui):
        ui.current_buffer.toggle_all_headers()


@registerCommand(MODE, 'sign', forced={'action': 'sign'}, arguments=[
    (['keyid'], {'nargs': argparse.REMAINDER, 'help': 'which key id to use'})],
    help='mark mail to be signed before sending')
@registerCommand(MODE, 'unsign', forced={'action': 'unsign'},
                 help='mark mail not to be signed before sending')
@registerCommand(MODE, 'togglesign', forced={'action': 'toggle'}, arguments=[
    (['keyid'], {'nargs': argparse.REMAINDER, 'help': 'which key id to use'})],
    help='toggle sign status')
class SignCommand(Command):
    """toggle signing this email"""
    repeatable = True

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
                    key = crypto.get_key(keyid, validate=True, sign=True)
                except GPGProblem, e:
                    envelope.sign = False
                    ui.notify(e.message, priority='error')
                    return
                envelope.sign_key = key
        else:
            envelope.sign_key = None

        # reload buffer
        ui.current_buffer.rebuild()


@registerCommand(MODE, 'encrypt', forced={'action': 'encrypt'}, arguments=[
    (['--trusted'], {'action': 'store_true', 'help': 'only add trusted keys'}),
    (['keyids'], {'nargs': argparse.REMAINDER,
                  'help': 'keyid of the key to encrypt with'})],
    help='request encryption of message before sendout')
@registerCommand(MODE, 'unencrypt', forced={'action': 'unencrypt'},
                 help='remove request to encrypt message before sending')
@registerCommand(MODE, 'toggleencrypt', forced={'action': 'toggleencrypt'},
                 arguments=[
                     (['--trusted'], {'action': 'store_true',
                                      'help': 'only add trusted keys'}),
                     (['keyids'], {'nargs': argparse.REMAINDER,
                      'help': 'keyid of the key to encrypt with'})],
                 help='toggle if message should be encrypted before sendout')
@registerCommand(MODE, 'rmencrypt', forced={'action': 'rmencrypt'},
                 arguments=[
                     (['keyids'], {'nargs': argparse.REMAINDER,
                      'help': 'keyid of the key to encrypt with'})],
                 help='do not encrypt to given recipient key')
class EncryptCommand(Command):
    def __init__(self, action=None, keyids=None, trusted=False, **kwargs):
        """
        :param action: wether to encrypt/unencrypt/toggleencrypt
        :type action: str
        :param keyid: the id of the key to encrypt
        :type keyid: str
        :param trusted: wether to filter keys and only use trusted ones
        :type trusted: bool
        """

        self.encrypt_keys = keyids
        self.action = action
        self.trusted = trusted
        Command.__init__(self, **kwargs)

    @inlineCallbacks
    def apply(self, ui):
        envelope = ui.current_buffer.envelope
        if self.action == 'rmencrypt':
            try:
                for keyid in self.encrypt_keys:
                    tmp_key = crypto.get_key(keyid)
                    del envelope.encrypt_keys[crypto.hash_key(tmp_key)]
            except GPGProblem as e:
                ui.notify(e.message, priority='error')
            if not envelope.encrypt_keys:
                envelope.encrypt = False
            ui.current_buffer.rebuild()
            return
        elif self.action == 'encrypt':
            encrypt = True
        elif self.action == 'unencrypt':
            encrypt = False
        elif self.action == 'toggleencrypt':
            encrypt = not envelope.encrypt
        envelope.encrypt = encrypt
        if encrypt:
            if not self.encrypt_keys:
                for recipient in envelope.headers['To'][0].split(','):
                    if not recipient:
                        continue
                    match = re.search("<(.*@.*)>", recipient)
                    if match:
                        recipient = match.group(1)
                    self.encrypt_keys.append(recipient)

            logging.debug("encryption keys: " + str(self.encrypt_keys))
            keys = yield get_keys(ui, self.encrypt_keys,
                                  signed_only=self.trusted)
            if self.trusted:
                logging.debug("filtered encrytion keys: " +
                              " ".join(x.uids[0].uid for x in keys.values()))
            if keys:
                envelope.encrypt_keys.update(keys)
            else:
                envelope.encrypt = False
        if not envelope.encrypt:
            # This is an extra conditional as it can even happen if encrypt is
            # True.
            envelope.encrypt_keys = {}
        # reload buffer
        ui.current_buffer.rebuild()
