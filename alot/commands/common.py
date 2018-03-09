# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

from . import Command

from .globals import PromptCommand


class RetagPromptCommand(Command):

    """prompt to retag selected threads\' tags"""
    def apply(self, ui):
        thread = ui.current_buffer.get_selected_thread()
        if not thread:
            return
        tags = []
        for tag in thread.get_tags():
            if ' ' in tag:
                tags.append('"%s"' % tag)
            # skip empty tags
            elif tag:
                tags.append(tag)
        initial_tagstring = ','.join(sorted(tags)) + ','
        return ui.apply_command(PromptCommand('retag ' + initial_tagstring))
