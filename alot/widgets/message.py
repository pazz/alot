# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
"""
Widgets specific to message viewer
"""
import urwid
import logging

from alot.settings import settings
from alot.db.utils import decode_header, X_SIGNATURE_MESSAGE_HEADER
from alot.widgets.globals import AttachmentWidget
from alot.db.utils import extract_body


class SimpleDictList(urwid.Pile):
    """
    :class:`SimpleTree` that displays key-value pairs.

    The structure will obey the Tree API but will not actually be a tree
    but a flat list: It contains one top-level node (displaying the k/v pair in
    Columns) per pair. That is, the root will be the first pair,
    its sibblings will be the other pairs and first|last_child will always
    be None.
    """
    def __init__(self, content, key_attr, value_attr, gaps_attr=None):
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
        max_key_len = 1
        structure = []
        # calc max length of key-string
        for key, value in content:
            if len(key) > max_key_len:
                max_key_len = len(key)
        for key, value in content:
            # todo : even/odd
            keyw = ('fixed', max_key_len + 1,
                    urwid.Text((key_attr, key)))
            valuew = urwid.Text((value_attr, value))
            line = urwid.Columns([keyw, valuew])
            if gaps_attr is not None:
                line = urwid.AttrMap(line, gaps_attr)
            structure.append(line)
        urwid.Pile.__init__(self, structure)


class MessageViewer(urwid.ListBox):
    """
    :class:`Message` that displays contents of a single
    :class:`alot.db.Message`.
    """
    def __init__(self, message, odd=True):
        """
        :param message: Message to display
        :type message: alot.db.Message
        :param odd: theme summary widget as if this is an odd line
                    (in the message-pile)
        :type odd: bool
        """
        self._message = message
        self._odd = odd
        self.display_source = False
        self._bodytree = None
        self._sourcetree = None
        self.display_all_headers = False
        self._all_headers_tree = None
        self._default_headers_tree = None
        self.display_attachments = True
        self._attachments = None

        self._contentlist = urwid.SimpleListWalker(self._assemble_structure())
        urwid.ListBox.__init__(self, self._contentlist)

    def get_message(self):
        return self._message

    def refresh(self):
        self._summaryw = None
        self._contentlist[:] = self._assemble_structure()

    def debug(self):
        logging.debug('display_source %s' % self.display_source)
        logging.debug('display_all_headers %s' % self.display_all_headers)
        logging.debug('display_attachements %s' % self.display_attachments)
        logging.debug('AHT %s' % str(self._all_headers_tree))
        logging.debug('DHT %s' % str(self._default_headers_tree))

    def _assemble_structure(self):
        mainstruct = []
        if self.display_source:
            mainstruct.append(self._get_source())
        else:
            mainstruct.append(self._get_headers())

            attachmenttree = self._get_attachments()
            if attachmenttree is not None:
                mainstruct.append(attachmenttree)

            bodytree = self._get_body()
            if bodytree is not None:
                mainstruct.append(self._get_body())

        return [urwid.Pile(mainstruct)]

    def _get_source(self):
        if self._sourcetree is None:
            sourcetxt = self._message.get_email().as_string()
            # TODO: use theming?
            # att = settings.get_theming_attribute('thread', 'body')
            # att_focus = settings.get_theming_attribute('thread',
            # 'body_focus')
            # self._sourcetree = urwid.Text(sourcetxt, att, att_focus)
            self._sourcetree = urwid.Text(sourcetxt)
        return self._sourcetree

    def _get_body(self):
        if self._bodytree is None:
            bodytxt = extract_body(self._message.get_email())
            if bodytxt:
                # TODO: use theming?
                # att = settings.get_theming_attribute('thread', 'body')
                # att_focus = settings.get_theming_attribute(
                #     'thread', 'body_focus')
                # self._bodytree = MessageText(bodytxt, att, att_focus)
                self._bodytree = urwid.Text(bodytxt)
        return self._bodytree

    def _get_headers(self):
        if self.display_all_headers is True:
            if self._all_headers_tree is None:
                self._all_headers_tree = self.construct_header_pile()
            ret = self._all_headers_tree
        else:
            if self._default_headers_tree is None:
                headers = settings.get('displayed_headers')
                self._default_headers_tree = self.construct_header_pile(
                    headers)
            ret = self._default_headers_tree
        return ret

    def _get_attachments(self):
        if self._attachments is None:
            alist = []
            for a in self._message.get_attachments():
                alist.append(AttachmentWidget(a))
            if alist:
                self._attachments = urwid.Pile(alist)
        return self._attachments

    def construct_header_pile(self, headers=None, normalize=True):
        mail = self._message.get_email()
        lines = []

        if headers is None:
            # collect all header/value pairs in the order they appear
            headers = mail.keys()
            for key, value in mail.items():
                dvalue = decode_header(value, normalize=normalize)
                lines.append((key, dvalue))
        else:
            # only a selection of headers should be displayed.
            # use order of the `headers` parameter
            for key in headers:
                if key in mail:
                    if key.lower() in ['cc', 'bcc', 'to']:
                        values = mail.get_all(key)
                        values = [decode_header(
                            v, normalize=normalize) for v in values]
                        lines.append((key, ', '.join(values)))
                    else:
                        for value in mail.get_all(key):
                            dvalue = decode_header(value, normalize=normalize)
                            lines.append((key, dvalue))
                elif key.lower() == 'tags':
                    logging.debug('want tags header')
                    values = []
                    for t in self._message.get_tags():
                        tagrep = settings.get_tagstring_representation(t)
                        if t is not tagrep['translated']:
                            t = '%s (%s)' % (tagrep['translated'], t)
                        values.append(t)
                    lines.append((key, ', '.join(values)))

        # OpenPGP pseudo headers
        if mail[X_SIGNATURE_MESSAGE_HEADER]:
            lines.append(('PGP-Signature', mail[X_SIGNATURE_MESSAGE_HEADER]))

        key_att = settings.get_theming_attribute('thread', 'header_key')
        value_att = settings.get_theming_attribute('thread', 'header_value')
        gaps_att = settings.get_theming_attribute('thread', 'header')
        return SimpleDictList(lines, key_att, value_att, gaps_att)
