# Copyright (C) 2011-2020  Patrick Totzke <patricktotzke@gmail.com>
# Copyright © 2019-2020 Chloé Dequeker <contact@nelyah.eu>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
import logging
import re

from urwid import AttrSpec
from ..settings.const import settings


def parse_text_colour(line):
    """Get colour attribute for the line

    :param str line: line of text to be parsed
    :return: The theme attribute to apply
    """
    if settings.get('parse_quotes'):
        return parse_quotes(line)
    else:
        return None


def parse_quotes(line):
    """Search for quotes.
    Only search up to the 7th quote level.

    :param str line: The line of text to be parsed
    :return: Theming attribute, None if no quote are available
    """

    # The value is arbitrarily set because we need to define
    # the corresponding attributes in the theming configuration spec.
    max_quote_level = 7
    quote_colour = get_quote_colour(line, max_quote_level)

    if isinstance(quote_colour, AttrSpec):
        return quote_colour
    else:
        return None


def get_quote_colour(line, max_quote_level):
    """Cycle through quotation levels for the line

    :param str line: The line of text to be parsed
    :param int max_quote_level: Search for quotes up to that level
    :return: quote_colour (either string 'default' or an AttrSpec object)
    """
    symbol = settings.get('quote_symbol')
    quote_colour = None

    for quote_level in range(1, max_quote_level+1):
        quote_regex = r'^ *({} *){{{}}}'.format(symbol, quote_level)
        if re.match(quote_regex, line):
            logging.debug(
                'Requesting attribute quote_level_{}'.format(quote_level))
            quote_colour = settings.get_theming_attribute(
                'thread', 'quote_level_{}'.format(quote_level))

        else:
            # If there is no match at some point,
            # we simply use the last level match colour
            break
    return quote_colour
