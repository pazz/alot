# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file

"""
This contains alot-specific :class:`urwid.Widget` used in more than one mode.
"""
import re
import operator
import urwid

from ..helper import string_decode
from ..settings.const import settings
from ..db.attachment import Attachment
from ..errors import CompletionError


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
                 separator=' ', choices_to_return=None):
        self.choices = choices
        self.choices_to_return = choices_to_return or {}
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
        elif key in self.choices_to_return:
            self.callback(self.choices_to_return[key])
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
        :esc/ctrl g: calls 'on_exit' with value `None`, which can be
                     interpreted as cancellation
        :tab: calls the completer and tabs forward in the result list
        :shift tab: tabs backward in the result list
        :up/down: move in the local input history
        :ctrl f/b: moves curser one character to the right/left
        :meta f/b shift right/left: moves the cursor one word to the right/left
        :ctrl a/e: moves curser to the beginning/end of the input
        :ctrl d: deletes the character under the cursor
        :meta d: deletes everything from the cursor to the end of the next word
        :meta delete/backspace ctrl w: deletes everything from the cursor to
                                       the beginning of the current word
        :ctrl k: deletes everything from the cursor to the end of the input
        :ctrl u: deletes everything from the cursor to the beginning of the
                 input
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
        :param on_error: callback that handles
                         :class:`alot.errors.CompletionErrors`
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
        self.focus_in_clist = 0

        if not isinstance(edit_text, str):
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
                except CompletionError as e:
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
                if key == 'up':
                    self.historypos = (self.historypos - 1) % len(self.history)
                else:
                    self.historypos = (self.historypos + 1) % len(self.history)
                self.set_edit_text(self.history[self.historypos])
        elif key == 'enter':
            self.on_exit(self.edit_text)
        elif key in ('ctrl g', 'esc'):
            self.on_exit(None)
        elif key == 'ctrl a':
            self.set_edit_pos(0)
        elif key == 'ctrl e':
            self.set_edit_pos(len(self.edit_text))
        elif key == 'ctrl f':
            self.set_edit_pos(min(self.edit_pos+1, len(self.edit_text)))
        elif key == 'ctrl b':
            self.set_edit_pos(max(self.edit_pos-1, 0))
        elif key == 'ctrl k':
            self.edit_text = self.edit_text[:self.edit_pos]
        elif key == 'ctrl u':
            self.edit_text = self.edit_text[self.edit_pos:]
            self.set_edit_pos(0)
        elif key == 'ctrl d':
            self.edit_text = (self.edit_text[:self.edit_pos] +
                              self.edit_text[self.edit_pos+1:])
        elif key in ('meta f', 'shift right'):
            self.move_to_next_word(forward=True)
        elif key in ('meta b', 'shift left'):
            self.move_to_next_word(forward=False)
        elif key == 'meta d':
            start_pos = self.edit_pos
            end_pos = self.move_to_next_word(forward=True)
            if end_pos is not None:
                self.edit_text = (self.edit_text[:start_pos] +
                                  self.edit_text[end_pos:])
                self.set_edit_pos(start_pos)
        elif key in ('meta delete', 'meta backspace', 'ctrl w'):
            end_pos = self.edit_pos
            start_pos = self.move_to_next_word(forward=False)
            if start_pos is not None:
                self.edit_text = (self.edit_text[:start_pos] +
                                  self.edit_text[end_pos:])
                self.set_edit_pos(start_pos)
        else:
            result = urwid.Edit.keypress(self, size, key)
            self.completions = None
            return result

    def move_to_next_word(self, forward=True):
        if forward:
            match_iterator = re.finditer(r'(\b\W+|$)', self.edit_text,
                                         flags=re.UNICODE)
            match_positions = [m.start() for m in match_iterator]
            op = operator.gt
        else:
            match_iterator = re.finditer(r'(\w+\b|^)', self.edit_text,
                                         flags=re.UNICODE)
            match_positions = reversed([m.start() for m in match_iterator])
            op = operator.lt
        for pos in match_positions:
            if op(pos, self.edit_pos):
                self.set_edit_pos(pos)
                return pos


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
        # calc max length of key-string
        for key, value in lines:
            if len(key) > max_key_len:
                max_key_len = len(key)
        for key, value in lines:
            # todo : even/odd
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

    Attributes that should be considered publicly readable:
        :attr tag: the notmuch tag
        :type tag: str
    """

    def __init__(self, tag, fallback_normal=None, fallback_focus=None):
        self.tag = tag
        representation = settings.get_tagstring_representation(tag,
                                                               fallback_normal,
                                                               fallback_focus)
        self.translated = representation['translated']
        self.hidden = self.translated == ''
        self.txt = urwid.Text(self.translated, wrap='clip')
        self.__hash = hash((self.translated, self.txt))
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

    def set_focussed(self):
        self.set_attr_map(self.attmaps['focus'])

    def set_unfocussed(self):
        self.set_attr_map(self.attmaps['normal'])

    def __cmp(self, other, comparitor):
        """Shared comparison method."""
        if not isinstance(other, TagWidget):
            return NotImplemented

        self_len = len(self.translated)
        oth_len = len(other.translated)

        if (self_len == 1) is not (oth_len == 1):
            return comparitor(self_len, oth_len)
        return comparitor(self.translated.lower(), other.translated.lower())

    def __lt__(self, other):
        """Groups tags of 1 character first, then alphabetically.

        This groups tags unicode characters at the begnining.
        """
        return self.__cmp(other, operator.lt)

    def __gt__(self, other):
        return self.__cmp(other, operator.gt)

    def __ge__(self, other):
        return self.__cmp(other, operator.ge)

    def __le__(self, other):
        return self.__cmp(other, operator.le)

    def __eq__(self, other):
        if not isinstance(other, TagWidget):
            return NotImplemented
        if len(self.translated) != len(other.translated):
            return False
        return self.translated.lower() == other.translated.lower()

    def __ne__(self, other):
        if not isinstance(other, TagWidget):
            return NotImplemented
        return self.translated.lower() != other.translated.lower()

    def __hash__(self):
        return self.__hash
