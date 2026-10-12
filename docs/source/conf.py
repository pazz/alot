# alot documentation build configuration file
import pathlib
import tomllib
import importlib.metadata

pyproject = pathlib.Path(__file__).parent.parent.parent / "pyproject.toml"
with pyproject.open("rb") as f:
    project_data = tomllib.load(f)["project"]

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx']

# autodoc tweaks
autodoc_mock_imports = [
    'alot.settings.const',
    'configobj',
    'gpg',
    'magic',
    'urwid',
    'urwidtrees',
    'validate',
]

# show classes' docstrings _and_ constructors docstrings/parameters
autoclass_content = 'both'
autodoc_member_order = 'groupwise'

project = 'alot'
copyright = "Copyright (C) 2012-24 Patrick Totzke"
version = importlib.metadata.version("alot")
release = version

html_theme = 'default'
html_title = 'Alot User Manual'

# (source start file, name, description, authors, manual section)
man_pages = [
    ('manpage', 'alot', project_data["description"],
     [a["name"] for a in project_data["authors"]], 1),
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/', None),
    'notmuch': ('https://notmuch.readthedocs.org/en/latest/', None),
    'urwid': ('https://urwid.readthedocs.org/en/latest/', None),
}
