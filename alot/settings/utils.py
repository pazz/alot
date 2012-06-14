# Copyright (C) 2011-2012  Patrick Totzke <patricktotzke@gmail.com>
# This file is released under the GNU GPL, version 3 or a later revision.
# For further details see the COPYING file
from configobj import ConfigObj, ConfigObjError, flatten_errors
from validate import Validator
from errors import ConfigError


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
    except (ConfigObjError, IOError), e:
        raise ConfigError('Could not read "%s": %s' % (configpath, e))

    if specpath:
        validator = Validator()
        validator.functions.update(checks)
        results = config.validate(validator)

        if results != True:
            error_msg = 'Validation errors occurred:\n'
            for (section_list, key, _) in flatten_errors(config, results):
                if key is not None:
                    msg = 'key "%s" in section "%s" failed validation'
                    msg = msg % (key, ', '.join(section_list))
                else:
                    msg = 'section "%s" is malformed' % ', '.join(section_list)
                error_msg += msg + '\n'
            raise ConfigError(error_msg)
    return config
