from importlib.metadata import version, PackageNotFoundError

# this requires python >=3.8
try:
    __version__ = version("alot")
except PackageNotFoundError:
    # package is not installed
    pass


__productname__ = 'alot'
__description__ = "Terminal MUA using notmuch mail"
