# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2018 Dylan Baker
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from . import Command

from .globals import PromptCommand


class RetagPromptCommand(Command):

    """prompt to retag selected thread's or message's tags"""
    async def apply(self, ui):
        get_selected_item = getattr(ui.current_buffer, {
                'search': 'get_selected_thread',
                'thread': 'get_selected_message'}[ui.mode])
        item = get_selected_item()
        if not item:
            return
        tags = []
        for tag in item.get_tags():
            if ' ' in tag:
                tags.append('"%s"' % tag)
            # skip empty tags
            elif tag:
                tags.append(tag)
        initial_tagstring = ','.join(sorted(tags)) + ','
        r = await ui.apply_command(PromptCommand('retag ' + initial_tagstring))
        return r
