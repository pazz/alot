import logging
import re
from ..settings.const import settings

def parse_text_colour(line):
    """Return colour attribute as (attr, attr_focus)

    :line: line of text to be parsed
    :returns: attr

    """
    return parse_quotes(line)


def parse_quotes(line, max_quote_level=7):
    """Search for quotes. 

    :returns: attr, None if no quote are available

    """
    default_colour = settings.get_theming_attribute('thread', 'body')
    is_quoted = False
    quote_colour = None
    symbol = settings.get('quote_symbol')
    if symbol is None:
        symbol = r'>'
    for quote_level in range(1, max_quote_level+1):
        quote_regex = r'^\ *(' + symbol + '\ *){' + str(quote_level) + r'}'

        if re.match(quote_regex, line):
            is_quoted = True
            logging.info(f'Requesting attribute quote_level_{quote_level}')
            quote_colour_tmp = settings.get_theming_attribute('thread', f'quote_level_{quote_level}')

            if quote_colour_tmp is not None:
                quote_colour = quote_colour_tmp
        else:
        # If there is no match at some point, we just use the last level match colour
            break
    if is_quoted and quote_colour is not None:
        return quote_colour
    else:
        return default_colour
