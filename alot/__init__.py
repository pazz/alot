from importlib.metadata import version, PackageNotFoundError

# this requires python >=3.8
try:
    __version__ = version("alot")
except PackageNotFoundError:
    # package is not installed
    pass


__productname__ = 'alot'
# -__copyright__ = "Copyright (C) 2012-21 Patrick Totzke"
# __author__ = "Patrick Totzke"
# __author_email__ = "patricktotzke@gmail.com"
__description__ = "Terminal MUA using notmuch mail"
# __url__ = "https://github.com/pazz/alot"
# __license__ = "Licensed under the GNU GPL v3+."
