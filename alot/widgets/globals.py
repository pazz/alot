# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""
This contains alot-specific :class:`urwid.Widget` used in more than one mode.
"""
import urwid

from alot.helper import string_decode
from alot.settings import settings
from alot.db.attachment import Attachment
from alot.errors import CompletionError


class AttachmentWidget(urwid.WidgetWrap):
    """
    one-line summary of an :class:`~alot.db.attachment.Attachment`.
    """
    def __init__(self, attachment, selectable=True):
        self._selectable = selectable
        self.attachment = attachment
        if not isinstance(attachment, Attachment):
            self.attachment = Attachment(self.attachment)
        att = settings.get_theming_attribute('thread', 'attachment')
        focus_att = settings.get_theming_attribute('thread',
                                                   'attachment_focus')
        widget = urwid.AttrMap(urwid.Text(self.attachment.__str__()),
                               att, focus_att)
        urwid.WidgetWrap.__init__(self, widget)

    def get_attachment(self):
        return self.attachment

    def selectable(self):
        return self._selectable

    def keypress(self, size, key):
        return key


class ChoiceWidget(urwid.Text):
    def __init__(self, choices, callback, cancel=None, select=None,
                 separator=' '):
        self.choices = choices
        self.callback = callback
        self.cancel = cancel
        self.select = select
        self.separator = separator

        items = []
        for k, v in choices.items():
            if v == select and select is not None:
                items += ['[', k, ']:', v]
            else:
                items += ['(', k, '):', v]
            items += [self.separator]
        urwid.Text.__init__(self, items)

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == 'enter' and self.select is not None:
            self.callback(self.select)
        elif key == 'esc' and self.cancel is not None:
            self.callback(self.cancel)
        elif key in self.choices:
            self.callback(self.choices[key])
        else:
            return key


class CompleteEdit(urwid.Edit):
    """
    This is a vamped-up :class:`urwid.Edit` widget that allows for
    tab-completion using :class:`~alot.completion.Completer` objects

    These widgets are meant to be used as user input prompts and hence
    react to 'return' key presses by calling a 'on_exit' callback
    that processes the current text value.

    The interpretation of some keypresses is hard-wired:
        :enter: calls 'on_exit' callback with current value
        :esc: calls 'on_exit' with value `None`, which can be interpreted
              as cancelation
        :tab: calls the completer and tabs forward in the result list
        :shift tab: tabs backward in the result list
        :up/down: move in the local input history
        :ctrl a/e: moves curser to the beginning/end of the input
    """
    def __init__(self, completer, on_exit,
                 on_error=None,
                 edit_text=u'',
                 history=None,
                 **kwargs):
        """
        :param completer: completer to use
        :type completer: alot.completion.Completer
        :param on_exit: "enter"-callback that interprets the input (str)
        :type on_exit: callable
        :param on_error: callback that handles :class:`completion errors <alot.errors.CompletionErrors>`
        :type on_error: callback
        :param edit_text: initial text
        :type edit_text: str
        :param history: initial command history
        :type history: list or str
        """
        self.completer = completer
        self.on_exit = on_exit
        self.on_error = on_error
        self.history = list(history)  # we temporarily add stuff here
        self.historypos = None

        if not isinstance(edit_text, unicode):
            edit_text = string_decode(edit_text)
        self.start_completion_pos = len(edit_text)
        self.completions = None
        urwid.Edit.__init__(self, edit_text=edit_text, **kwargs)

    def keypress(self, size, key):
        # if we tabcomplete
        if key in ['tab', 'shift tab'] and self.completer:
            # if not already in completion mode
            if self.completions is None:
                self.completions = [(self.edit_text, self.edit_pos)]
                try:
                    self.completions += self.completer.complete(self.edit_text,
                                                                self.edit_pos)
                    self.focus_in_clist = 1
                except CompletionError, e:
                    if self.on_error is not None:
                        self.on_error(e)

            else:  # otherwise tab through results
                if key == 'tab':
                    self.focus_in_clist += 1
                else:
                    self.focus_in_clist -= 1
            if len(self.completions) > 1:
                ctext, cpos = self.completions[self.focus_in_clist %
                                               len(self.completions)]
                self.set_edit_text(ctext)
                self.set_edit_pos(cpos)
            else:
                self.completions = None
        elif key in ['up', 'down']:
            if self.history:
                if self.historypos is None:
                    self.history.append(self.edit_text)
                    self.historypos = len(self.history) - 1
                if key == 'cursor up':
                    self.historypos = (self.historypos + 1) % len(self.history)
                else:
                    self.historypos = (self.historypos - 1) % len(self.history)
                self.set_edit_text(self.history[self.historypos])
        elif key == 'enter':
            self.on_exit(self.edit_text)
        elif key == 'esc':
            self.on_exit(None)
        elif key == 'ctrl a':
            self.set_edit_pos(0)
        elif key == 'ctrl e':
            self.set_edit_pos(len(self.edit_text))
        else:
            result = urwid.Edit.keypress(self, size, key)
            self.completions = None
            return result


class HeadersList(urwid.WidgetWrap):
    """ renders a pile of header values as key/value list """
    def __init__(self, headerslist, key_attr, value_attr, gaps_attr=None):
        """
        :param headerslist: list of key/value pairs to display
        :type headerslist: list of (str, str)
        :param key_attr: theming attribute to use for keys
        :type key_attr: urwid.AttrSpec
        :param value_attr: theming attribute to use for values
        :type value_attr: urwid.AttrSpec
        :param gaps_attr: theming attribute to wrap lines in
        :type gaps_attr: urwid.AttrSpec
        """
        self.headers = headerslist
        self.key_attr = key_attr
        self.value_attr = value_attr
        pile = urwid.Pile(self._build_lines(headerslist))
        if gaps_attr is None:
            gaps_attr = key_attr
        pile = urwid.AttrMap(pile, gaps_attr)
        urwid.WidgetWrap.__init__(self, pile)

    def __str__(self):
        return str(self.headers)

    def _build_lines(self, lines):
        max_key_len = 1
        headerlines = []
        #calc max length of key-string
        for key, value in lines:
            if len(key) > max_key_len:
                max_key_len = len(key)
        for key, value in lines:
            ##todo : even/odd
            keyw = ('fixed', max_key_len + 1,
                    urwid.Text((self.key_attr, key)))
            valuew = urwid.Text((self.value_attr, value))
            line = urwid.Columns([keyw, valuew])
            headerlines.append(line)
        return headerlines


class TagWidget(urwid.AttrMap):
    """
    text widget that renders a tagstring.

    It looks up the string it displays in the `tags` section
    of the config as well as custom theme settings for its tag.
    """
    def __init__(self, tag, fallback_normal=None, fallback_focus=None):
        self.tag = tag
        representation = settings.get_tagstring_representation(tag,
                                                               fallback_normal,
                                                               fallback_focus)
        self.translated = representation['translated']
        self.hidden = self.translated == ''
        self.txt = urwid.Text(self.translated, wrap='clip')
        normal_att = representation['normal']
        focus_att = representation['focussed']
        self.attmaps = {'normal': normal_att, 'focus': focus_att}
        urwid.AttrMap.__init__(self, self.txt, normal_att, focus_att)

    def set_map(self, attrstring):
        self.set_attr_map({None: self.attmaps[attrstring]})

    def width(self):
        # evil voodoo hotfix for double width chars that may
        # lead e.g. to strings with length 1 that need width 2
        return self.txt.pack()[0]

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def get_tag(self):
        return self.tag

    def set_focussed(self):
        self.set_attr_map(self.attmap['focus'])

    def set_unfocussed(self):
        self.set_attr_map(self.attmap['normal'])
