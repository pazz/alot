# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Alot is a terminal mail user agent built on the notmuch indexer (via the `notmuch2` cffi bindings), urwid/urwidtrees for the UI, and an asyncio event loop.

## Commands

```sh
python3 -m pytest                                   # full test suite (tests are unittest-style)
python3 -m pytest tests/db/test_utils.py::TestExtractBodyPart::test_simple_iso_8859_1_mail
python3 -m unittest                                 # what CONTRIBUTING.md documents
nix build .#checks.x86_64-linux.types               # mypy check, as run in CI
make -C docs cleanall html                          # rebuild docs, including generated tables
```

CI runs `ruff check` with its default rules (pyflakes and error-class pycodestyle checks); fuller PEP8 is advisory (pycodestyle config in `setup.cfg`, E501 ignored). Document signatures with Sphinx field lists (`:param:`, `:type:`, `:rtype:`).

mypy runs strictly only on the modules listed under `[[tool.mypy.overrides]]` in `pyproject.toml`; the Nix `types` check in `flake.nix` hard-codes the same file list, so keep both in sync when adding typed modules.

## Generated docs are checked in CI

`docs/source/generate_commands.py` and `generate_configs.py` render the command reference (`docs/source/usage/modes/*.rst`) and config option tables (`docs/source/configuration/*_table`) from the code. CI regenerates them and fails on `git diff`. After changing a command's `@registerCommand` arguments/help or anything in `alot/defaults/*.spec`, run `make -C docs cleanall html` and commit the regenerated files.

## Architecture

**Commands and modes.** Every user action is a `Command` subclass in `alot/commands/<mode>.py`, registered with `@registerCommand(mode, name, arguments=[...])`. Registration fills the global `COMMANDS[mode][name] = (class, argparser, forced_kwargs)`. Modes are `search`, `thread`, `envelope`, `bufferlist`, `taglist`, `namedqueries`, `global`; a buffer's `modename` selects the mode, and lookup falls back to `global`. `commandfactory()` parses a command-line string, instantiates the command with argparse results as kwargs, and attaches user `pre_`/`post_<mode>_<cmd>` hooks. `forced` kwargs let one class back several commands (e.g. reply vs. group reply).

**UI loop.** `alot/ui.py:UI` owns the urwid main loop, the buffer list, prompts and notifications. Keys are resolved through `settings.get_keybinding(mode, keyseq)` into command lines, then `apply_commandline` (supports `;`-separated sequences) and `apply_command` run them; `Command.apply(ui)` may be `async`. Commands interact with the user through `ui.prompt`, `ui.choice` and `ui.notify`.

**Database.** `alot/db/manager.py:DBManager` opens notmuch read-only for every query. Writes (tag, untag, add/remove message, named queries) are appended to `writequeue` and applied by `flush()`, each in its own atomic transaction; on a locked DB the entry stays queued for a later retry. `alot/db/{thread,message}.py` wrap notmuch objects; `alot/db/utils.py` does MIME body extraction, charset decoding, mailcap rendering and crypto verification/decryption; `alot/db/envelope.py` is an unsent mail being composed.

**Settings.** `alot.settings.const.settings` is a module-level `SettingsManager` singleton imported everywhere. It validates the user config against configobj specs in `alot/defaults/` (`alot.rc.spec`, `theme.spec`, default bindings and theme), reads parts of notmuch's own config, builds `Account` objects (`alot/account.py`, sending via sendmail), and loads the optional user hooks file (`hooksfile` option) as a Python module exposed through `settings.get_hook(name)`.

## Tests

Many tests patch the global `settings` singleton with `unittest.mock`; `tests/utilities.py` has shared helpers (class-level cleanups, `async_test`, mock key and UI factories).

## Scope

Per CONTRIBUTING.md, contact management, fetching and sending mail are out of scope. Keep commits small and focused; for new features update `docs/source/usage` as well.

## Change policy

- `main` is the default branch; `master` is the old human-only line and stays untouched. One concern per branch off `main`, one PR each into `main`. Ask before pushing.
- Small is beautiful: the smallest clean diff that solves the problem. Prefer deletion, stdlib and existing helpers; no speculative parameters, layers or abstractions.
- Bug fixes come with a regression test that fails without the fix.
- Do not edit `NEWS` in branches; it is updated in one go before a release. Put a ready-to-paste "NEWS: ..." line for user-facing changes in the PR description instead.

## Reviews

This section applies to AI-assisted contributions; human contributors are welcome without it.

Reviewers are the agents in `.claude/agents/`. Each runs in a fresh context and gets only the branch or commit and the issue or PR numbers, never the author's summary, so that the author's assumptions do not frame the review. Run the agents of a tier in parallel. CI already runs the test matrix (including Python 3.10 with the oldest dependencies), ruff, mypy and the generated docs; the reviewers cover what CI cannot (tests failing without the fix, the tests CI skips, behaviour, design, security).

- **Trivial** (documentation, comments): `review-correctness`.
- **Normal** (everything else, including CI workflows): `review-correctness` and `review-design`.
- **High risk**: also `review-security`, a second opinion from a non-Anthropic model, and a request for a human co-maintainer's review in the PR. High risk means anything that handles untrusted mail content (headers, MIME parts, attachments, HTML, terminal output), temporary files, shell, mailcap or external commands, crypto, or signals and process lifetime.

When unsure, take the higher tier.

The second opinion uses the Copilot CLI with only its read-only file tools (`view`, `glob`, `rg`): no shell, no writes, no network, no MCP servers. The model is named because Copilot defaults to Claude models; `gpt-6-luna` or any other non-Anthropic model the plan offers will do. Give it the diff and the issue or PR text, or a statement of the goal:

```sh
copilot -s --model gpt-6-luna --available-tools view glob rg \
  -p "$(awk 'f>=2; /^---$/{f++}' .claude/agents/review-correctness.md)
You can only read files; skip the checks that need running code.
Diff: $(git diff origin/main...HEAD)
Issue: $(gh issue view N --comments)"
```

For a PR use `gh pr view N --comments`; with neither, replace that line with a statement of the goal. Alternatively, once the PR is open, request Copilot's online review with `gh pr edit N --add-reviewer @copilot`.

Every finding is either fixed or left with a reason. The PR description ends with a "Review findings and resolution" section: for each reviewer, its findings and what was done with each (fixed, or left and why).
