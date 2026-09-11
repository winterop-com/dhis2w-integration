# CLAUDE.md

Guidance for Claude Code working in this repository.

## The rules live in the host

This repository follows the conventions of the dhis2w host workspace
(https://github.com/winterop-com/dhis2w). Read its `CLAUDE.md` and apply it here: no emojis
anywhere, greenfield voice (state what the code does now, never what it used to do), Pydantic
for all structured data with no `dict`s and no `@dataclass`es, a one-line Google-style docstring
on every module, class and function, full descriptive names with no abbreviations, Python 3.13+
with type annotations everywhere and a 120-column line length, Typer for every CLI, pytest for
every test, `uv` for everything Python, and conventional commits with no AI attribution.

`make lint` runs ruff, mypy and pyright, all strict; `make test` assembles the ecosystem and
runs every suite. Run both before opening a pull request.

## What is different here

- This is not a workspace. It is one distribution, `dhis2w-integration`, that depends on the
  host's packages and on every pack from git.
- `ecosystem.yaml` is the source of truth for what gets assembled. A new pack is one entry
  there, one dependency and one source in `pyproject.toml`, and one name in
  `tests/test_merged_host.py`. `scripts/run_integration.py` stays generic: it never learns a
  pack's name.
- `src/dhis2w_integration/bench/` is the benchmark harness, carried over from the host's
  `dhis2w-bench`. It measures the assembled surface, which is why it lives here.
- No `uv.lock` is committed: the sources ride `main` and the lock is resolved fresh by
  `make lock`.
