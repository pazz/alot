# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from configobj import ConfigObj, ConfigObjError, flatten_errors
from validate import Validator
from errors import ConfigError
from urwid import AttrSpec


def read_config(configpath=None, specpath=None, checks={}):
    """
    get a (validated) config object for given config file path.

    :param configpath: path to config-file
    :type configpath: str
    :param specpath: path to spec-file
    :type specpath: str
    :param checks: custom checks to use for validator.
        see `validate docs <http://www.voidspace.org.uk/python/validate.html>`_
    :type checks: dict str->callable,
    :raises: :class:`~alot.settings.errors.ConfigError`
    :rtype: `configobj.ConfigObj`
    """
    try:
        config = ConfigObj(infile=configpath, configspec=specpath,
                           file_error=True, encoding='UTF8')
    except ConfigObjError as e:
        raise ConfigError(e)
    except IOError:
        raise ConfigError('Could not read %s and/or %s' % (configpath, specpath))
    except UnboundLocalError:
        # this works around a bug in configobj
        msg = '%s is malformed. Check for sections without parents..'
        raise ConfigError(msg % configpath)

    if specpath:
        validator = Validator()
        validator.functions.update(checks)
        try:
            results = config.validate(validator, preserve_errors=True)
        except ConfigObjError as e:
            raise ConfigError(e.message)

        if results is not True:
            error_msg = ''
            for (section_list, key, res) in flatten_errors(config, results):
                if key is not None:
                    if res is False:
                        msg = 'key "%s" in section "%s" is missing.'
                        msg = msg % (key, ', '.join(section_list))
                    else:
                        msg = 'key "%s" in section "%s" failed validation: %s'
                        msg = msg % (key, ', '.join(section_list), res)
                else:
                    msg = 'section "%s" is missing' % '.'.join(section_list)
                error_msg += msg + '\n'
            raise ConfigError(error_msg)
    return config


def resolve_att(a, fallback):
    """ replace '' and 'default' by fallback values """
    if a is None:
        return fallback
    if a.background in ['default', '']:
        bg = fallback.background
    else:
        bg = a.background
    if a.foreground in ['default', '']:
        fg = fallback.foreground
    else:
        fg = a.foreground
    return AttrSpec(fg, bg)
