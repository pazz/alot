# Copyright (C) 2011-2018  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import urwid
from notmuch2 import NotmuchError

from .buffer import Buffer
from ..settings.const import settings
from ..walker import IterableWalker
from ..widgets.search import ThreadlineWidget


class SearchBuffer(Buffer):
    """shows a result list of threads for a query"""

    modename = 'search'
    threads = []
    _REVERSE = {'oldest_first': 'newest_first',
                'newest_first': 'oldest_first'}

    def __init__(self, ui, initialquery='', sort_order=None):
        self.dbman = ui.dbman
        self.ui = ui
        # We store a list of notmuch query strings and this buffer will
        # display the results for each query one after the other
        self.querystrings = [initialquery]
        default_order = settings.get('search_threads_sort_order')
        self.sort_order = sort_order or default_order
        self.result_count = 0
        self.search_threads_rebuild_limit = \
            settings.get('search_threads_rebuild_limit')
        self.search_threads_move_last_limit = \
            settings.get('search_threads_move_last_limit')
        self.isinitialized = False
        self.threadlist = None
        self.rebuild()
        Buffer.__init__(self, ui, self.body)

    def __str__(self):
        formatstring = '[search] for "%s" (%d message%s)'
        return formatstring % ('" + "'.join(self.querystrings),
                               self.result_count,
                               's' if self.result_count > 1 else '')

    def get_info(self):
        info = {}
        info['querystring'] = '" + "'.join(self.querystrings)
        info['result_count'] = self.result_count
        info['result_count_positive'] = 's' if self.result_count > 1 else ''
        return info

    def rebuild(self, reverse=False, restore_focus=True):
        self.isinitialized = True
        self.reversed = reverse
        selected_thread = None

        if reverse:
            order = self._REVERSE[self.sort_order]
        else:
            order = self.sort_order

        if restore_focus and self.threadlist:
            selected_thread = self.get_selected_thread()

        self.result_count = 0
        self.threadlist = None
        for query in self.querystrings:
            try:
                self.result_count += self.dbman.count_messages(query)
                threads = self.dbman.get_threads(
                    query, order)
            except NotmuchError:
                self.ui.notify('malformed query string: %s' % query,
                               'error')
                self.listbox = urwid.ListBox([])
                self.body = self.listbox
                return

            iterablewalker = IterableWalker(threads, ThreadlineWidget,
                                            dbman=self.dbman,
                                            reverse=reverse)
            if self.threadlist:
                self.threadlist.append(iterablewalker)
            else:
                self.threadlist = iterablewalker

        self.listbox = urwid.ListBox(self.threadlist)
        self.body = self.listbox

        if selected_thread:
            self.focus_thread(selected_thread)

    def get_selected_threadline(self):
        """
        returns curently focussed :class:`alot.widgets.ThreadlineWidget`
        from the result list.
        """
        threadlinewidget, _ = self.threadlist.get_focus()
        return threadlinewidget

    def get_selected_thread(self):
        """returns currently selected :class:`~alot.db.Thread`"""
        threadlinewidget = self.get_selected_threadline()
        thread = None
        if threadlinewidget:
            thread = threadlinewidget.get_thread()
        return thread

    def consume_pipe(self):
        while not self.threadlist.empty:
            self.threadlist._get_next_item()

    def consume_pipe_until(self, predicate, limit=0):
        n = limit
        while not limit or n > 0:
            if self.threadlist.empty \
               or predicate(self.threadlist._get_next_item()):
                break
            n -= 1

    def focus_first(self):
        if not self.reversed:
            self.body.set_focus(0)
        else:
            self.rebuild(reverse=False, restore_focus=False)
            self.body.set_focus(0)

    def focus_last(self):
        if self.reversed:
            self.body.set_focus(0)
        elif self.search_threads_move_last_limit == 0 \
                or self.result_count < self.search_threads_move_last_limit \
                or self.sort_order not in self._REVERSE:
            self.consume_pipe()
            num_lines = len(self.threadlist.get_lines())
            self.body.set_focus(num_lines - 1)
        else:
            self.rebuild(reverse=True, restore_focus=False)
            self.body.set_focus(0)

    def focus_thread(self, thread):
        tid = thread.get_thread_id()
        self.consume_pipe_until(lambda w:
                                w and w.get_thread().get_thread_id() == tid,
                                self.search_threads_rebuild_limit)

        for pos, threadlinewidget in enumerate(self.threadlist.get_lines()):
            if threadlinewidget.get_thread().get_thread_id() == tid:
                self.body.set_focus(pos)
                break
