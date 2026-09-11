# dhis2w-integration

The control center for the dhis2w plugin ecosystem. This is the one place aware of every pack at
once -- it assembles the host and every pack into a single environment and runs everyone
together to prove they still compose.

## The principle it protects

dhis2w-core knows nothing about any pack. Every out-of-repo pack -- `dhis2w-security` today,
more to come -- lives only in its own repository and self-tests there, against nothing but its
own dependencies. The integration is the only place the whole set is installed side by side, so
it is the only place that can prove they still compose: that every pack's contribution lands in
one plugin host without colliding, that one Typer application takes every command group, and
that one FastMCP server takes every tool.

## What is here

- **`ecosystem.yaml`** -- the manifest: every component and the ref it tracks, the source of
  truth for what gets assembled. `dhis2w` (the host workspace) is `role: runtime`, installed as
  dependencies and never cloned; each pack is `role: pack`, cloned and self-tested here.
  `dhis2w-security` is the first; a future pack becomes real with a single entry.
- **`pyproject.toml`** -- the assembled runtime: the host surfaces (`dhis2w-cli`, `dhis2w-mcp`,
  `dhis2w-fhir`, `dhis2w-mcp-router`) plus every pack, wired through `[tool.uv.sources]` as git
  dependencies on `branch = "main"`, unpinned, so the integration always assembles the latest
  ecosystem.
- **`scripts/run_integration.py`** -- the runner. It reads the manifest, clones each pack,
  installs it editable into the assembled environment, runs the pack's own suite there, and then
  runs this repository's tests. It is generic: it iterates the packs the manifest names and has
  no per-pack knowledge.
- **`src/dhis2w_integration/bench/`** -- the LLM benchmark harness: local models and cloud Claude
  driven over the `d2w` CLI, the mcp-bridge, the full MCP server and the MCP router. It belongs
  here because a benchmark measures the assembled surface, which only this repository holds.
- **`tests/`** -- the integration's own tests: the merged plugin host is coherent for v41, v42
  and v43, and the harness's pure functions still hold.

## Running it locally

```sh
make test
```

One target, one green or red:

1. resolve the ecosystem's branch tips and install them into `.venv`;
2. clone every `role: pack` in `ecosystem.yaml` into `checkouts/` (gitignored), at its ref;
3. install each pack editable into the assembled environment;
4. run each pack's own suite there (`make test` in its checkout, or `pytest` when it has none);
5. run the integration's own tests.

A pack whose checkout is already present is reused, and one carrying local changes is left where
it is -- which is what lets a local run substitute a sibling working tree for a clone. Other
targets: `make sync`, `make clone`, `make bench`, `make lint`, `make clean`.

No `uv.lock` is committed. Nothing in the ecosystem is published, the sources ride `main`, and a
committed lock would freeze an ecosystem that moves every day; `make lock` resolves it fresh and
`make sync` installs from it.

## The benchmark harness

```sh
make bench MODULE=general ARGS="google/gemma-4-26b-a4b-qat"
```

`MODULE` names a module of `dhis2w_integration.bench`, each of which is its own entry point:
`backend` lists the models the local backend has installed, `general` measures coding capability
with no DHIS2 in the loop, `bridge` and `round` drive the mcp-bridge, `mcp` and `router` drive
the full MCP surface and the router over it, `composite` and `longcontext` are the hard multi-
object writes and the needle-in-a-haystack retrieval, and the `claude_*` modules are the cloud
peers of the same suites. They spawn the servers with `uv run --directory`, which is this
repository -- the assembled environment is what they measure.

## Adding a pack

One entry in `ecosystem.yaml`:

```yaml
  dhis2w-something:
    repo: https://github.com/winterop-com/dhis2w-something
    ref: main
    role: pack
```

Add it to `dependencies` and `[tool.uv.sources]` in `pyproject.toml` so it is installed with the
rest, and to `EXPECTED_NAMES` in `tests/test_merged_host.py` so its absence is a failure. The
runner needs no edit: it clones, installs and tests whatever the manifest names.

## CI

The assembled check is expensive -- clone every pack, install the whole host from git, run every
suite -- and GitHub Actions minutes are scarce, so `.github/workflows/integration.yml` never
runs on push. Per-commit safety belongs to each repository's own CI: `dhis2w` tests itself on
its pushes, each pack tests itself on its own. The integration is the integration truth, caught
weekly and on demand.

The components are public, so the git dependencies uv resolves and the pack clones the runner
makes need no credentials and the workflow needs no secret.

## Licence

Copyright (c) 2026 Morten Olav Hansen. All rights reserved. See [LICENSE](LICENSE).

The source is published for reference only: no licence to use, copy, modify or distribute it is
granted, and any use beyond reading requires written permission.
