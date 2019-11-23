# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse
import datetime
import email
import email.policy
import glob
import logging
import os
import re
import tempfile
import textwrap
import traceback

from . import Command, registerCommand
from . import globals
from . import utils
from .. import buffers
from .. import commands
from .. import crypto
from ..account import SendingMailFailed, StoreMailError
from ..db.errors import DatabaseError
from ..errors import GPGProblem, ConversionError
from ..helper import string_decode
from ..helper import call_cmd
from ..helper import split_commandstring
from ..settings.const import settings
from ..settings.errors import NoMatchingAccount
from ..utils import argparse as cargparse
from ..utils.collections import OrderedSet


MODE = 'envelope'


@registerCommand(
    MODE, 'attach',
    arguments=[(['path'], {'help': 'file(s) to attach (accepts wildcads)'})])
class AttachCommand(Command):
    """attach files to the mail"""
    repeatable = True

    def __init__(self, path, **kwargs):
        """
        :param path: files to attach (globable string)
        :type path: str
        """
        Command.__init__(self, **kwargs)
        self.path = path

    def apply(self, ui):
        envelope = ui.current_buffer.envelope

        files = [g for g in glob.glob(os.path.expanduser(self.path))
                 if os.path.isfile(g)]
        if not files:
            ui.notify('no matches, abort')
            return

        logging.info("attaching: %s", files)
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

    async def apply(self, ui):
        value = ui.current_buffer.envelope.get(self.key, '')
        cmdstring = 'set %s %s' % (self.key, value)
        await ui.apply_command(globals.PromptCommand(cmdstring))


@registerCommand(MODE, 'save')
class SaveCommand(Command):
    """save draft"""
    async def apply(self, ui):
        envelope = ui.current_buffer.envelope

        # determine account to use
        if envelope.account is None:
            try:
                envelope.account = settings.account_matching_address(
                    envelope['From'], return_default=True)
            except NoMatchingAccount:
                ui.notify('no accounts set.', priority='error')
                return
        account = envelope.account

        if account.draft_box is None:
            msg = 'abort: Account for {} has no draft_box'
            ui.notify(msg.format(account.address), priority='error')
            return

        mail = envelope.construct_mail()
        # store mail locally
        path = account.store_draft_mail(
            mail.as_string(policy=email.policy.SMTP))

        msg = 'draft saved successfully'

        # add mail to index if maildir path available
        if path is not None:
            ui.notify(msg + ' to %s' % path)
            logging.debug('adding new mail to index')
            try:
                ui.dbman.add_message(path, account.draft_tags + envelope.tags)
                await ui.apply_command(globals.FlushCommand())
                await ui.apply_command(commands.globals.BufferCloseCommand())
            except DatabaseError as e:
                logging.error(str(e))
                ui.notify('could not index message:\n%s' % str(e),
                          priority='error',
                          block=True)
        else:
            await ui.apply_command(commands.globals.BufferCloseCommand())


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

    def _get_keys_addresses(self):
        addresses = set()
        for key in self.envelope.encrypt_keys.values():
            for uid in key.uids:
                addresses.add(uid.email)
        return addresses

    def _get_recipients_addresses(self):
        tos = self.envelope.headers.get('To', [])
        ccs = self.envelope.headers.get('Cc', [])
        return {a for (_, a) in email.utils.getaddresses(tos + ccs)}

    def _is_encrypted_to_all_recipients(self):
        recipients_addresses = self._get_recipients_addresses()
        keys_addresses = self._get_keys_addresses()
        return recipients_addresses.issubset(keys_addresses)

    async def apply(self, ui):
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
                if (await ui.choice(warning, cancel='no',
                                    msg_position='left')) == 'no':
                    return

            # don't do anything if another SendCommand is in the middle of
            # sending the message and we were triggered accidentally
            if self.envelope.sending:
                logging.debug('sending this message already!')
                return

            # Before attempting to construct mail, ensure that we're not trying
            # to encrypt a message with a BCC, since any BCC recipients will
            # receive a message that they cannot read!
            if self.envelope.headers.get('Bcc') and self.envelope.encrypt:
                warning = textwrap.dedent("""\
                    Any BCC recipients will not be able to decrypt this
                    message. Do you want to send anyway?""").replace('\n', ' ')
                if (await ui.choice(warning, cancel='no',
                                    msg_position='left')) == 'no':
                    return

            # Check if an encrypted message is indeed encrypted to all its
            # recipients.
            if (self.envelope.encrypt
                    and not self._is_encrypted_to_all_recipients()):
                warning = textwrap.dedent("""\
                    Message is not encrypted to all recipients. This means that
                    not everyone will be able to decode and read this message.
                    Do you want to send anyway?""").replace('\n', ' ')
                if (await ui.choice(warning, cancel='no',
                                    msg_position='left')) == 'no':
                    return

            clearme = ui.notify('constructing mail (GPG, attachments)…',
                                timeout=-1)

            try:
                self.mail = self.envelope.construct_mail()
                self.mail = self.mail.as_string(policy=email.policy.SMTP)
            except GPGProblem as e:
                ui.clear_notify([clearme])
                ui.notify(str(e), priority='error')
                return

            ui.clear_notify([clearme])

        # determine account to use for sending
        msg = self.mail
        if not isinstance(msg, email.message.Message):
            msg = email.message_from_string(
                self.mail, policy=email.policy.SMTP)
        address = msg.get('Resent-From', False) or msg.get('From', '')
        logging.debug("FROM: \"%s\"" % address)
        try:
            account = settings.account_matching_address(address,
                                                        return_default=True)
        except NoMatchingAccount:
            ui.notify('no accounts set', priority='error')
            return
        logging.debug("ACCOUNT: \"%s\"" % account.address)

        # send out
        clearme = ui.notify('sending..', timeout=-1)
        if self.envelope is not None:
            self.envelope.sending = True
        try:
            await account.send_mail(self.mail)
        except SendingMailFailed as e:
            if self.envelope is not None:
                self.envelope.account = account
                self.envelope.sending = False
            ui.clear_notify([clearme])
            logging.error(traceback.format_exc())
            errmsg = 'failed to send: {}'.format(e)
            ui.notify(errmsg, priority='error', block=True)
        except StoreMailError as e:
            ui.clear_notify([clearme])
            logging.error(traceback.format_exc())
            errmsg = 'could not store mail: {}'.format(e)
            ui.notify(errmsg, priority='error', block=True)
        else:
            initial_tags = []
            if self.envelope is not None:
                self.envelope.sending = False
                self.envelope.sent_time = datetime.datetime.now()
                initial_tags = self.envelope.tags
            logging.debug('mail sent successfully')
            ui.clear_notify([clearme])
            if self.envelope_buffer is not None:
                cmd = commands.globals.BufferCloseCommand(self.envelope_buffer)
                await ui.apply_command(cmd)
            ui.notify('mail sent successfully')
            if self.envelope is not None:
                if self.envelope.replied:
                    self.envelope.replied.add_tags(account.replied_tags)
                if self.envelope.passed:
                    self.envelope.passed.add_tags(account.passed_tags)

            # store mail locally
            # This can raise StoreMailError
            path = account.store_sent_mail(self.mail)

            # add mail to index if maildir path available
            if path is not None:
                logging.debug('adding new mail to index')
                ui.dbman.add_message(path, account.sent_tags + initial_tags)
                await ui.apply_command(globals.FlushCommand())


@registerCommand(MODE, 'edit', arguments=[
    (['--spawn'], {'action': cargparse.BooleanAction, 'default': None,
                   'help': 'spawn editor in new terminal'}),
    (['--refocus'], {'action': cargparse.BooleanAction, 'default': True,
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
        self.edit_part = None

        Command.__init__(self, **kwargs)

    async def apply(self, ui):
        ebuffer = ui.current_buffer
        if not self.envelope:
            self.envelope = ebuffer.envelope

        # determine editable headers
        edit_headers = OrderedSet(settings.get('edit_headers_whitelist'))
        if '*' in edit_headers:
            edit_headers = OrderedSet(self.envelope.headers)
        blacklist = set(settings.get('edit_headers_blacklist'))
        if '*' in blacklist:
            blacklist = set(self.envelope.headers)
        edit_headers = edit_headers - blacklist
        logging.info('editable headers: %s', edit_headers)

        def openEnvelopeFromTmpfile():
            # This parses the input from the tempfile.
            # we do this ourselves here because we want to be able to
            # just type utf-8 encoded stuff into the tempfile and let alot
            # worry about encodings.

            # get input
            # tempfile will be removed on buffer cleanup
            enc = settings.get('editor_writes_encoding')
            with open(self.envelope.tmpfile.name) as f:
                template = string_decode(f.read(), enc)

            # call post-edit translate hook
            translate = settings.get_hook('post_edit_translate')
            if translate:
                template = translate(template, ui=ui, dbm=ui.dbman)
            logging.debug('target bodypart: %s' % self.edit_part)
            self.envelope.parse_template(template,
                                         only_body=self.edit_only_body,
                                         target_body=self.edit_part)
            if self.openNew:
                ui.buffer_open(buffers.EnvelopeBuffer(ui, self.envelope))
            else:
                ebuffer.envelope = self.envelope
                ebuffer.rebuild()

        # decode header
        headertext = ''
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

        # determine which part to edit
        # TODO: add config option to enforce plaintext here
        if self.edit_part is None:
            # I can't access ebuffer in my constructor, hence the check here
            if isinstance(ebuffer, buffers.EnvelopeBuffer):
                if ebuffer.displaypart in ['html', 'src']:
                    self.edit_part = 'html'
                    logging.debug('displaypart: %s' % ebuffer.displaypart)
        if self.edit_part == 'html':
            bodytext = self.envelope.body_html
            logging.debug('editing HTML source')
        else:
            self.edit_part = 'plaintext'
            bodytext = self.envelope.body_txt
            logging.debug('editing plaintext')

        # determine editable content
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
        with tempfile.NamedTemporaryFile(
                delete=False, prefix='alot.', suffix='.eml') as tmpfile:
            tmpfile.write(content.encode('utf-8'))
            tmpfile.flush()
            self.envelope.tmpfile = tmpfile
        if old_tmpfile:
            os.unlink(old_tmpfile.name)
        cmd = globals.EditCommand(self.envelope.tmpfile.name,
                                  on_success=openEnvelopeFromTmpfile,
                                  spawn=self.force_spawn,
                                  thread=self.force_spawn,
                                  refocus=self.refocus)
        await ui.apply_command(cmd)


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

    async def apply(self, ui):
        envelope = ui.current_buffer.envelope
        if self.reset:
            if self.key in envelope:
                del envelope[self.key]
        envelope.add(self.key, self.value)
        # FIXME: handle BCC as well
        # Currently we don't handle bcc because it creates a side channel leak,
        # as the key of the person BCC'd will be available to other recievers,
        # defeating the purpose of BCCing them
        if self.key.lower() in ['to', 'from', 'cc'] and envelope.encrypt:
            await utils.update_keys(ui, envelope)
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

    async def apply(self, ui):
        del ui.current_buffer.envelope[self.key]
        # FIXME: handle BCC as well
        # Currently we don't handle bcc because it creates a side channel leak,
        # as the key of the person BCC'd will be available to other recievers,
        # defeating the purpose of BCCing them
        if self.key.lower() in ['to', 'from', 'cc']:
            await utils.update_keys(ui, ui.current_buffer.envelope)
        ui.current_buffer.rebuild()


@registerCommand(MODE, 'toggleheaders')
class ToggleHeaderCommand(Command):
    """toggle display of all headers"""
    repeatable = True

    def apply(self, ui):
        ui.current_buffer.toggle_all_headers()


@registerCommand(
    MODE, 'sign', forced={'action': 'sign'},
    arguments=[
        (['keyid'],
         {'nargs': argparse.REMAINDER, 'help': 'which key id to use'})],
    help='mark mail to be signed before sending')
@registerCommand(MODE, 'unsign', forced={'action': 'unsign'},
                 help='mark mail not to be signed before sending')
@registerCommand(
    MODE, 'togglesign', forced={'action': 'toggle'}, arguments=[
        (['keyid'],
         {'nargs': argparse.REMAINDER, 'help': 'which key id to use'})],
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
        envelope = ui.current_buffer.envelope
        # sign status
        if self.action == 'sign':
            sign = True
        elif self.action == 'unsign':
            sign = False
        elif self.action == 'toggle':
            sign = not envelope.sign
        envelope.sign = sign

        if sign:
            if self.keyid:
                # try to find key if hint given as parameter
                keyid = str(' '.join(self.keyid))
                try:
                    envelope.sign_key = crypto.get_key(keyid, validate=True,
                                                       sign=True)
                except GPGProblem as e:
                    envelope.sign = False
                    ui.notify(str(e), priority='error')
                    return
            else:
                if envelope.account is None:
                    try:
                        envelope.account = settings.account_matching_address(
                            envelope['From'])
                    except NoMatchingAccount:
                        envelope.sign = False
                        ui.notify('Unable to find a matching account',
                                  priority='error')
                        return
                acc = envelope.account
                if not acc.gpg_key:
                    envelope.sign = False
                    msg = 'Account for {} has no gpg key'
                    ui.notify(msg.format(acc.address), priority='error')
                    return
                envelope.sign_key = acc.gpg_key
        else:
            envelope.sign_key = None

        # reload buffer
        ui.current_buffer.rebuild()


@registerCommand(
    MODE, 'encrypt', forced={'action': 'encrypt'}, arguments=[
        (['--trusted'], {'action': 'store_true',
                         'help': 'only add trusted keys'}),
        (['keyids'], {'nargs': argparse.REMAINDER,
                      'help': 'keyid of the key to encrypt with'})],
    help='request encryption of message before sendout')
@registerCommand(
    MODE, 'unencrypt', forced={'action': 'unencrypt'},
    help='remove request to encrypt message before sending')
@registerCommand(
    MODE, 'toggleencrypt', forced={'action': 'toggleencrypt'},
    arguments=[
        (['--trusted'], {'action': 'store_true',
                         'help': 'only add trusted keys'}),
        (['keyids'], {'nargs': argparse.REMAINDER,
                      'help': 'keyid of the key to encrypt with'})],
    help='toggle if message should be encrypted before sendout')
@registerCommand(
    MODE, 'rmencrypt', forced={'action': 'rmencrypt'},
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

    async def apply(self, ui):
        envelope = ui.current_buffer.envelope
        if self.action == 'rmencrypt':
            try:
                for keyid in self.encrypt_keys:
                    tmp_key = crypto.get_key(keyid)
                    del envelope.encrypt_keys[tmp_key.fpr]
            except GPGProblem as e:
                ui.notify(str(e), priority='error')
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
        if encrypt:
            if self.encrypt_keys:
                for keyid in self.encrypt_keys:
                    tmp_key = crypto.get_key(keyid)
                    envelope.encrypt_keys[tmp_key.fpr] = tmp_key
            else:
                await utils.update_keys(ui, envelope, signed_only=self.trusted)
        envelope.encrypt = encrypt
        if not envelope.encrypt:
            # This is an extra conditional as it can even happen if encrypt is
            # True.
            envelope.encrypt_keys = {}
        # reload buffer
        ui.current_buffer.rebuild()


@registerCommand(
    MODE, 'tag', forced={'action': 'add'},
    arguments=[(['tags'], {'help': 'comma separated list of tags'})],
    help='add tags to message',
)
@registerCommand(
    MODE, 'retag', forced={'action': 'set'},
    arguments=[(['tags'], {'help': 'comma separated list of tags'})],
    help='set message tags',
)
@registerCommand(
    MODE, 'untag', forced={'action': 'remove'},
    arguments=[(['tags'], {'help': 'comma separated list of tags'})],
    help='remove tags from message',
)
@registerCommand(
    MODE, 'toggletags', forced={'action': 'toggle'},
    arguments=[(['tags'], {'help': 'comma separated list of tags'})],
    help='flip presence of tags on message',
)
class TagCommand(Command):

    """manipulate message tags"""
    repeatable = True

    def __init__(self, tags='', action='add', **kwargs):
        """
        :param tags: comma separated list of tagstrings to set
        :type tags: str
        :param action: adds tags if 'add', removes them if 'remove', adds tags
                       and removes all other if 'set' or toggle individually if
                       'toggle'
        :type action: str
        """
        assert isinstance(tags, str), 'tags should be a unicode string'
        self.tagsstring = tags
        self.action = action
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        ebuffer = ui.current_buffer
        envelope = ebuffer.envelope
        tags = {t for t in self.tagsstring.split(',') if t}
        old = set(envelope.tags)
        if self.action == 'add':
            new = old.union(tags)
        elif self.action == 'remove':
            new = old.difference(tags)
        elif self.action == 'set':
            new = tags
        elif self.action == 'toggle':
            new = old.symmetric_difference(tags)
        envelope.tags = sorted(new)
        # reload buffer
        ui.current_buffer.rebuild()


@registerCommand(
    MODE, 'html2txt', forced={'action': 'html2txt'},
    arguments=[(['cmd'], {'nargs': argparse.REMAINDER,
                           'help': 'converter command to use'})],
    help='convert html to plaintext alternative',
)
@registerCommand(
    MODE, 'txt2html', forced={'action': 'txt2html'},
    arguments=[(['cmd'], {'nargs': argparse.REMAINDER,
                           'help': 'converter command to use'})],
    help='convert plaintext to html alternative',
)
class BodyConvertCommand(Command):
    def __init__(self, action=None, cmd=None):
        self.action = action
        self.cmd = cmd
        Command.__init__(self)

    def convert(self, cmdstring, inputstring):
        logging.debug("converting using %s" % cmdstring)
        cmdlist = split_commandstring(cmdstring)
        resultstring, errmsg, retval = call_cmd(cmdlist,
                                                stdin=inputstring)
        if retval != 0:
            msg = 'converter "%s" returned with ' % cmdstring
            msg += 'return code %d' % retval
            if errmsg:
                msg += ':\n%s' % errmsg
            raise ConversionError(msg)
        logging.debug("resultstring is \n" + resultstring)
        return resultstring

    def apply(self, ui):
        ebuffer = ui.current_buffer
        envelope = ebuffer.envelope

        if self.action is "txt2html":
            cmdstring = self.cmd or settings.get('envelope_txt2html')
            if cmdstring:
                envelope.body_html = self.convert(cmdstring, envelope.body_txt)

        elif self.action is "html2txt":
            cmdstring = self.cmd or settings.get('envelope_html2txt')
            if cmdstring:
                envelope.body_txt = self.convert(cmdstring, envelope.body_html)

        ui.current_buffer.rebuild()


@registerCommand(
    MODE, 'display', help='change which body alternative to display',
    arguments=[(['part'], {'help': 'part to show'})])
class ChangeDisplaymodeCommand(Command):

    """change wich body alternative is shown"""

    def __init__(self, part=None, **kwargs):
        """
        :param part: which part to show
        :type indent: 'plaintext', 'src', or 'html'
        """
        self.part = part
        Command.__init__(self, **kwargs)

    async def apply(self, ui):
        ebuffer = ui.current_buffer
        envelope = ebuffer.envelope

        # make sure that envelope has html part if requested here
        if self.part in ['html', 'src'] and not envelope.body_html:
            await ui.apply_command(BodyConvertCommand(action='txt2html'))

        ui.current_buffer.set_displaypart(self.part)
        ui.update()
