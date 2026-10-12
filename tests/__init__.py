# Keep tests independent of the mailcap files on the host system.
from alot.settings.const import settings
settings._mailcaps = {}
