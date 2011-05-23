import logging

import settings

defaulthooks = {}


def get_hook(name):
    logging.debug('looking for hook %s' % name)
    if name in settings.hooks:
        return settings.hooks[name]
    else:
        # TODO: parse hookdir for binaries?
        return None
