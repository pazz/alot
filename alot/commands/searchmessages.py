# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import argparse
import logging

from alot.commands import Command, registerCommand
from alot.commands.globals import MoveCommand
from alot.commands.thread import (
    ReplyCommand, ForwardCommand, EditNewCommand, PipeCommand, TagCommand,
    SaveAttachmentCommand, OpenAttachmentCommand)
from alot.utils.booleanaction import BooleanAction

from alot.widgets.globals import AttachmentWidget


MODE = 'searchmessages'


@registerCommand(MODE, 'move', help='move focus in search buffer',
                 arguments=[(['movement'], {
                             'nargs': argparse.REMAINDER,
                             'help': 'last'})])
class MoveFocusCommand(MoveCommand):

    def apply(self, ui):
        logging.debug(self.movement)
        tbuffer = ui.current_buffer
        if self.movement == 'last':
            tbuffer.focus_last()
            ui.update()
        elif self.movement == 'next' or self.movement == 'previous':
            ui.mainloop.process_input([self.movement])
            tbuffer.possible_message_focus_change()
            # tbuffer.focus_next()
        else:
            MoveCommand.apply(self, ui)


@registerCommand(MODE, 'reply', arguments=[
    (['--all'], {'action': 'store_true', 'help': 'reply to all'}),
    (['--list'], {'action': BooleanAction, 'default': None,
                  'dest': 'listreply', 'help': 'reply to list'}),
    (['--spawn'], {'action': BooleanAction, 'default': None,
                   'help': 'open editor in new window'})])
class SMReplyCommand(ReplyCommand):
    pass


@registerCommand(MODE, 'forward', arguments=[
    (['--attach'], {'action': 'store_true', 'help': 'attach original mail'}),
    (['--spawn'], {'action': BooleanAction, 'default': None,
                   'help': 'open editor in new window'})])
class SMForwardCommand(ForwardCommand):
    pass


# TODO: getting error when trying to edit a message made by someone
# that is not me, because cant find account settings.
# Does it happens on master?
@registerCommand(MODE, 'editnew', arguments=[
    (['--spawn'], {'action': BooleanAction, 'default': None,
                   'help': 'open editor in new window'})])
class SMEditNewCommand(EditNewCommand):
    pass


@registerCommand(MODE, 'pipeto', arguments=[
    (['cmd'], {'help': 'shellcommand to pipe to', 'nargs': '+'}),
    (['--all'], {'action': 'store_true', 'help': 'pass all messages'}),
    (['--format'], {'help': 'output format', 'default': 'raw',
                    'choices': ['raw', 'decoded', 'id', 'filepath']}),
    (['--separately'], {'action': 'store_true',
                        'help': 'call command once for each message'}),
    (['--background'], {'action': 'store_true',
                        'help': 'don\'t stop the interface'}),
    (['--add_tags'], {'action': 'store_true',
                      'help': 'add \'Tags\' header to the message'}),
    (['--shell'], {'action': 'store_true',
                   'help': 'let the shell interpret the command'}),
    (['--notify_stdout'], {'action': 'store_true',
                           'help': 'display cmd\'s stdout as notification'}),
],
)
class SMPipeCommand(PipeCommand):
    pass


@registerCommand(MODE, 'toggletags', forced={'action': 'toggle'}, arguments=[
    (['--all'], {'action': 'store_true',
     'help': 'tag all messages in thread'}),
    (['--no-flush'], {'action': 'store_false', 'dest': 'flush',
                      'help': 'postpone a writeout to the index'}),
    (['tags'], {'help': 'comma separated list of tags'})],
    help='flip presence of tags on message(s)',
)
class SMTagCommand(TagCommand):
    pass


@registerCommand(MODE, 'save', arguments=[
    (['--all'], {'action': 'store_true', 'help': 'save all attachments'}),
    (['path'], {'nargs': '?', 'help': 'path to save to'})])
class SMSaveAttachmentCommand(SaveAttachmentCommand):
    pass


@registerCommand(MODE, 'select')
class SelectCommand(Command):

    """select focussed element. The fired action depends on the focus:
        - if message summary, this toggles visibility of the message,
        - if attachment line, this opens the attachment"""
    def apply(self, ui):
        focus = ui.get_deep_focus()
        if isinstance(focus, AttachmentWidget):
            logging.info('open attachment')
            ui.apply_command(OpenAttachmentCommand(focus.get_attachment()))


@registerCommand(MODE, 'togglesource', forced={'raw': 'toggle'}, arguments=[
    (['query'], {'help': 'query used to filter messages to affect',
                 'nargs': '*'}),
], help='display message source')
@registerCommand(MODE, 'toggleheaders', forced={'all_headers': 'toggle'},
                 arguments=[
                     (['query'], {
                         'help': 'query used to filter messages to affect',
                         'nargs': '*'}),
                 ],
                 help='display all headers')
class ChangeDisplaymodeCommand(Command):

    """toggle source or headers"""
    repeatable = True

    def __init__(self, query=None, visible=None, raw=None, all_headers=None,
                 **kwargs):
        """
        :param query: notmuch query string used to filter messages to affect
        :type query: str
        :param visible: unfold if `True`, fold if `False`, ignore if `None`
        :type visible: True, False, 'toggle' or None
        :param raw: display raw message text.
        :type raw: True, False, 'toggle' or None
        :param all_headers: show all headers (only visible if not in raw mode)
        :type all_headers: True, False, 'toggle' or None
        """
        self.raw = raw
        self.all_headers = all_headers
        Command.__init__(self, **kwargs)

    def apply(self, ui):
        mv = ui.current_buffer.get_message_viewer()
        raw = not mv.display_source if self.raw == 'toggle' else self.raw
        all_headers = not mv.display_all_headers \
            if self.all_headers == 'toggle' else self.all_headers

        if raw is not None:
            mv.display_source = raw
        if all_headers is not None:
            mv.display_all_headers = all_headers
        mv.refresh()

# TODO: implement bounce, print, refine
# TODO: maybe also implement refineprompt, retagprompt, remove?
