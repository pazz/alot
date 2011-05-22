import logging

import settings

defaulthooks = {}

def get_hook(name):
    logging.debug('looking for hook %s'%name)
    if settings.hooks.has_key(name):
        return settings.hooks[name]
    else:
        #TODO: parse hookdir for binaries?
        return None
