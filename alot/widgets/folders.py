# -*- coding: utf-8 -*-

import logging
import urwid
from urwidtrees import Tree
from alot.settings.const import settings


class FolderWidget(urwid.WidgetWrap):
    """
    special widget for displaying folder, so we can distinguish between
    empty and focused folders
    """
    def __init__(self, folder):
        self.folder = folder
        self.txt = urwid.Text(unicode(folder), wrap='clip')
        if folder.unread_count > 0:
            normal_att = settings.get_theming_attribute('folders', 'line')
        else:
            normal_att = settings.get_theming_attribute('folders',
                                                        'line_empty')
        focus_att = settings.get_theming_attribute('folders', 'line_focus')
        line = urwid.AttrMap(self.txt, normal_att, focus_att)
        logging.debug("line = %s", line)
        urwid.WidgetWrap.__init__(self, line)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class FoldersTree(Tree):
    """
    Implementation of Tree interface for maildir folders
    """
    def __init__(self, account):
        self._account = account
        self.root_folder = account.get_root()
        self.root = None
        self._parent_of = {}
        self._first_child_of = {}
        self._last_child_of = {}
        self._next_sibling_of = {}
        self._prev_sibling_of = {}
        self._folders = {}

        def accumulate(folder, odd=True):
            """recursively read msg and its replies"""
            folder_id = folder.get_id()
            logging.debug("folder = %s", folder)
            self._folders[folder_id] = FolderWidget(folder)
            odd = not odd
            last = None
            self._first_child_of[folder_id] = None
            for child_folder in self._account.get_children(folder):
                child_folder_id = child_folder.get_id()
                if self._first_child_of[folder_id] is None:
                    self._first_child_of[folder_id] = child_folder_id
                self._parent_of[child_folder_id] = folder_id
                self._prev_sibling_of[child_folder_id] = last
                self._next_sibling_of[last] = child_folder_id
                last = child_folder_id
                odd = accumulate(child_folder, odd)
            self._last_child_of[folder_id] = last
            return odd

        last = None
        f_id = self.root_folder.get_id()
        self._prev_sibling_of[f_id] = last
        self._next_sibling_of[last] = f_id
        accumulate(self.root_folder)
        self.root = f_id
        last = f_id
        self._next_sibling_of[last] = None

    def next_unread(self, pos):
        folder = self._folders[pos].folder
        return self._account.get_next_unread(folder).get_id()

    def previous_unread(self, pos):
        folder = self._folders[pos].folder
        return self._account.get_previous_unread(folder).get_id()

    # Tree API
    def __getitem__(self, pos):
        return self._folders.get(pos)

    def parent_position(self, pos):
        return self._parent_of.get(pos, None)

    def first_child_position(self, pos):
        return self._first_child_of.get(pos, None)

    def last_child_position(self, pos):
        return self._last_child_of.get(pos, None)

    def next_sibling_position(self, pos):
        return self._next_sibling_of.get(pos, None)

    def prev_sibling_position(self, pos):
        return self._prev_sibling_of.get(pos, None)
