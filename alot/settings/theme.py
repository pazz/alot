# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os
from urwid import AttrSpec, AttrSpecError

from utils import read_config
from checks import align_mode
from checks import attr_triple
from checks import width_tuple
from checks import force_list
from errors import ConfigError

DEFAULTSPATH = os.path.join(os.path.dirname(__file__), '..', 'defaults')


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
                        msg = 'missing threadline parts: %s' % difference
                        raise ConfigError(msg)

    def _by_colour(self, triple, colour):
        return triple[self._colours.index(colour)]

    def get_attribute(self, mode, name, colourmode):
        """
        returns requested attribute

        :param mode: ui-mode (e.g. `search`,`thread`...)
        :type mode: str
        :param name: identifier of the atttribute
        :type name: str
        :param colourmode: colour mode; in [1, 16, 256]
        :type colourmode: int
        """
        return self._config[mode][name][self._colours.index(colourmode)]

    def get_threadline_theming(self, thread, colourmode):
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
            if candidatename.startswith('threadline') and\
               (not candidatename == 'threadline') and\
               matches(candidate, thread):
                    match = candidate
                    break

        # fill in values
        res = {}
        res['normal'] = pickcolour(match.get('normal') or default['normal'])
        res['focus'] = pickcolour(match.get('focus') or default['focus'])
        res['parts'] = match.get('parts') or default['parts']
        for part in res['parts']:
            partsec = match.get(part) or default[part]
            res[part] = {}
            res[part]['width'] = partsec.get('width') or ('fit', 0, 0)
            res[part]['alignment'] = partsec.get('alignment')
            normal_triple = partsec.get('normal') or default['normal']
            res[part]['normal'] = pickcolour(normal_triple)
            focus_triple = partsec.get('focus') or default['focus']
            res[part]['focus'] = pickcolour(focus_triple)
        return res
