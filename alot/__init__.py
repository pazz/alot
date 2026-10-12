from importlib.metadata import version, PackageNotFoundError
from typing import Optional

__version__: Optional[str]
try:
    __version__ = version("alot")
except PackageNotFoundError:
    # package is not installed
    __version__ = None
