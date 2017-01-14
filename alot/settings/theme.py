# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from __future__ import absolute_import

import os

from .utils import read_config
from .checks import align_mode
from .checks import attr_triple
from .checks import width_tuple
from .checks import force_list
from .errors import ConfigError

DEFAULTSPATH = os.path.join(os.path.dirname(__file__), '..', 'defaults')
DUMMYDEFAULT = ('default',) * 6


class Theme(object):
    """Colour theme"""
    def __init__(self, path):
        """
        :param path: path to theme file
        :type path: str
        :raises: :class:`~alot.settings.errors.ConfigError`
        """
        self._spec = os.path.join(DEFAULTSPATH, 'theme.spec')
        self._config = read_config(path, self._spec,
                                   checks={'align': align_mode,
                                           'widthtuple': width_tuple,
                                           'force_list': force_list,
                                           'attrtriple': attr_triple})
        self._colours = [1, 16, 256]
        # make sure every entry in 'order' lists have their own subsections
        threadline = self._config['search']['threadline']
        for sec in self._config['search']:
            if sec.startswith('threadline'):
                tline = self._config['search'][sec]
                if tline['parts'] is not None:
                    listed = set(tline['parts'])
                    here = set(tline.sections)
                    indefault = set(threadline.sections)
                    diff = listed.difference(here.union(indefault))
                    if diff:
                        msg = 'missing threadline parts: %s' % ', '.join(diff)
                        raise ConfigError(msg)

    def get_attribute(self, colourmode, mode, name, part=None):
        """
        returns requested attribute

        :param mode: ui-mode (e.g. `search`,`thread`...)
        :type mode: str
        :param name: of the atttribute
        :type name: str
        :param colourmode: colour mode; in [1, 16, 256]
        :type colourmode: int
        :rtype: urwid.AttrSpec
        """
        thmble = self._config[mode][name]
        if part is not None:
            thmble = thmble[part]
        thmble = thmble or DUMMYDEFAULT
        return thmble[self._colours.index(colourmode)]

    def get_threadline_theming(self, thread, colourmode):
        """
        look up how to display a Threadline wiidget in search mode
        for a given thread.

        :param thread: Thread to theme Threadline for
        :type thread: alot.db.thread.Thread
        :param colourmode: colourmode to use, one of 1,16,256.
        :type colourmode: int

        This will return a dict mapping
            :normal: to `urwid.AttrSpec`,
            :focus: to `urwid.AttrSpec`,
            :parts: to a list of strings indentifying subwidgets
                    to be displayed in this order.

        Moreover, for every part listed this will map 'part' to a dict mapping
            :normal: to `urwid.AttrSpec`,
            :focus: to `urwid.AttrSpec`,
            :width: to a tuple indicating the width of the subpart.
                    This is either `('fit', min, max)` to force the widget
                    to be at least `min` and at most `max` characters wide,
                    or `('weight', n)` which makes it share remaining space
                    with other 'weight' parts.
            :alignment: where to place the content if shorter than the widget.
                        This is either 'right', 'left' or 'center'.
        """
        def pickcolour(triple):
            return triple[self._colours.index(colourmode)]

        def matches(sec, thread):
            if sec.get('tagged_with') is not None:
                if not set(sec['tagged_with']).issubset(thread.get_tags()):
                    return False
            if sec.get('query') is not None:
                if not thread.matches(sec['query']):
                    return False
            return True

        default = self._config['search']['threadline']
        match = default

        candidates = self._config['search'].sections
        for candidatename in candidates:
            candidate = self._config['search'][candidatename]
            if (candidatename.startswith('threadline') and
                    (not candidatename == 'threadline') and
                    matches(candidate, thread)):
                match = candidate
                break

        # fill in values
        res = {}
        res['normal'] = pickcolour(match.get('normal') or default['normal'])
        res['focus'] = pickcolour(match.get('focus') or default['focus'])
        res['parts'] = match.get('parts') or default['parts']
        for part in res['parts']:
            defaultsec = default.get(part)
            partsec = match.get(part) or {}

            def fill(key, fallback=None):
                pvalue = partsec.get(key) or defaultsec.get(key)
                return pvalue or fallback

            res[part] = {}
            res[part]['width'] = fill('width', ('fit', 0, 0))
            res[part]['alignment'] = fill('alignment', 'right')
            res[part]['normal'] = pickcolour(fill('normal'))
            res[part]['focus'] = pickcolour(fill('focus'))
        return res
