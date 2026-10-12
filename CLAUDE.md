# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Alot is a terminal mail user agent built on the notmuch indexer (via the `notmuch2` cffi bindings), urwid/urwidtrees for the UI, and an asyncio event loop. Python >= 3.10.

## Commands

```sh
python3 -m pytest                                   # full test suite (tests are unittest-style)
python3 -m pytest tests/db/test_utils.py::TestExtractBodyPart::test_simple_iso_8859_1_mail
python3 -m unittest                                 # what CONTRIBUTING.md documents
python3 -m build                                    # build sdist/wheel (version from setuptools-scm)
nix build .#checks.x86_64-linux.types               # mypy check, as run in CI
make -C docs cleanall html                          # rebuild docs, including generated tables
```

Style is PEP8 checked with pycodestyle (config in `setup.cfg`, E501 ignored). Document signatures with Sphinx field lists (`:param:`, `:type:`, `:rtype:`).

mypy runs strictly only on the modules listed under `[[tool.mypy.overrides]]` in `pyproject.toml`; the Nix `types` check in `flake.nix` hard-codes the same file list, so keep both in sync when adding typed modules.

## Generated docs are checked in CI

`docs/source/generate_commands.py` and `generate_configs.py` render the command reference (`docs/source/usage/modes/*.rst`) and config option tables (`docs/source/configuration/*_table`) from the code. CI regenerates them and fails on `git diff`. After changing a command's `@registerCommand` arguments/help or anything in `alot/defaults/*.spec`, run `make -C docs cleanall html` and commit the regenerated files.

## Architecture

**Commands and modes.** Every user action is a `Command` subclass in `alot/commands/<mode>.py`, registered with `@registerCommand(mode, name, arguments=[...])`. Registration fills the global `COMMANDS[mode][name] = (class, argparser, forced_kwargs)`. Modes are `search`, `thread`, `envelope`, `bufferlist`, `taglist`, `namedqueries`, `global`; a buffer's `modename` selects the mode, and lookup falls back to `global`. `commandfactory()` parses a command-line string, instantiates the command with argparse results as kwargs, and attaches user `pre_`/`post_<mode>_<cmd>` hooks. `forced` kwargs let one class back several commands (e.g. reply vs. group reply).

**UI loop.** `alot/ui.py:UI` owns the urwid main loop, the buffer list, prompts and notifications. Keys are resolved through `settings.get_keybinding(mode, keyseq)` into command lines, then `apply_commandline` (supports `;`-separated sequences) and `apply_command` run them; `Command.apply(ui)` may be `async`. Commands interact with the user through `ui.prompt`, `ui.choice` and `ui.notify`.

**Buffers and widgets.** `alot/buffers/` has one buffer class per mode; `alot/widgets/` holds the urwid widgets they render. Thread mode uses urwidtrees for nested message/MIME trees.

**Database.** `alot/db/manager.py:DBManager` opens notmuch read-only for every query. Writes (tag, untag, add/remove message, named queries) are appended to `writequeue` and applied by `flush()`, each in its own atomic transaction; on a locked DB the entry stays queued for a later retry. `alot/db/{thread,message}.py` wrap notmuch objects; `alot/db/utils.py` does MIME body extraction, charset decoding, mailcap rendering and crypto verification/decryption; `alot/db/envelope.py` is an unsent mail being composed.

**Settings.** `alot.settings.const.settings` is a module-level `SettingsManager` singleton imported everywhere. It validates the user config against configobj specs in `alot/defaults/` (`alot.rc.spec`, `theme.spec`, default bindings and theme), reads parts of notmuch's own config, builds `Account` objects (`alot/account.py`, sending via sendmail), and loads the optional user hooks file (`hooksfile` option) as a Python module exposed through `settings.get_hook(name)`.

**Startup.** `alot/__main__.py` parses CLI args, reads settings, creates the `DBManager` and the `UI`. urwid runs on the same asyncio event loop (`urwid.AsyncioEventLoop`).

## Tests

Tests live in `tests/`, mirroring the package layout. Test mails are in `tests/static/mail/`. Many tests patch the global `settings` singleton with `unittest.mock`; `tests/utilities.py` has shared helpers (class-level cleanups, `async_test`, mock key and UI factories).

## Scope

Per CONTRIBUTING.md, contact management, fetching and sending mail are out of scope. Keep commits small and focused; for new features update `docs/source/usage` as well.

## Change policy

- `master` is the human-only line and stays untouched. AI-assisted work integrates into `main` (branched from `master`); one concern per branch off `main`, one PR each into `main`. Ask before pushing.
- Small is beautiful: the smallest clean diff that solves the problem. Prefer deletion, stdlib and existing helpers; no speculative parameters, layers or abstractions.
- Bug fixes come with a regression test that fails without the fix.
- Every branch gets two fresh-context reviews before a PR: one for correctness, one that doubts the change for over-engineering.
