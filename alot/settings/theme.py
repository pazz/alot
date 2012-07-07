# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import os
import logging
from urwid import AttrSpec, AttrSpecError

from utils import read_config
from checks import align_mode
from checks import attr_triple
from checks import width_tuple
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
                                           'attrtriple': attr_triple})
        self._colours = [1, 16, 256]
        # make sure every entry in 'order' lists have their own subsections
        for sec in self._config['search']:
            if sec.startswith('threadline'):
                threadline = self._config['search'][sec]
                if 'order' in threadline:
                    listed = set(threadline['order'])
                    present = set(threadline.sections)
                    difference = listed.difference(present)
                    if difference:
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

    def get_threadline_structure(self, thread, colourmode):
        def pickcolour(triple):
            return triple[self._colours.index(colourmode)]

        def matches(sec, thread):
            if 'tags_contain' in sec.scalars:
                if not set(sec['tags_contain']).issubset(thread.get_tags()):
                    return False
            if 'query' in sec.scalars:
                if not thread.matches(sec['query']):
                    return False
            return True

        default = self._config['search']['threadline'].copy()
        match = default

        for candidatename in self._config['search'].sections:
            candidate = self._config['search'][candidatename]
            logging.debug('testing:%s' % candidatename)
            if candidatename.startswith('threadline') and\
               matches(candidate, thread):
                    match = candidate
                    break
        #logging.debug('match: %s' % match)

        # fill in values
        res = {}
        res['normal'] = pickcolour(match.get('normal', default['normal']))
        res['focus'] = pickcolour(match.get('focus', default['focus']))
        res['order'] = match.get('order', default['order'])
        for part in res['order']:
            res[part] = {}
            res[part]['width'] = match[part].get('width') or ('fit', 0, 0)
            res[part]['alignment'] = match[part].get('alignment')
            res[part]['normal'] = pickcolour(match[part].get('normal', default['normal']))
            res[part]['focus'] = pickcolour(match[part].get('focus', default['focus']))
        logging.debug(res)
        return res
