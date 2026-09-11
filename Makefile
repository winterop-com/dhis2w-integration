# The integration control center. `make test` assembles the ecosystem and reports one green/red.

UV ?= uv

.PHONY: help lock sync clone test bench lint clean

help:
	@echo "dhis2w-integration"
	@echo "  lock    Resolve the ecosystem's branch tips into uv.lock"
	@echo "  sync    Install the assembled runtime and dev tooling into .venv"
	@echo "  clone   Clone (or refresh) every pack named in ecosystem.yaml into checkouts/"
	@echo "  test    Assemble everything and run every suite: one green or red"
	@echo "  bench   Run one benchmark module: make bench MODULE=general ARGS=\"<model> ...\""
	@echo "  lint    ruff + mypy + pyright over this repository's own sources"
	@echo "  clean   Remove the cloned packs, the environment, and the caches"

# Resolve the ecosystem's branch tips into uv.lock. The lock is not committed -- the sources
# ride main, so it is resolved fresh, and nothing in the ecosystem is published yet.
lock:
	$(UV) lock --upgrade

# Install the assembled runtime and dev tooling into .venv, from a lock resolved at the tips:
# a stale lock would test an old ecosystem.
sync: lock
	$(UV) sync

# Clone (or refresh) every pack named in ecosystem.yaml into checkouts/, without running.
clone: sync
	$(UV) run python scripts/run_integration.py --clone-only

# Assemble and run everything: clone each pack, install it into the assembled environment, run
# its own suite there, then run this repository's tests. One command, one result.
test: sync
	$(UV) run python scripts/run_integration.py

# Run one benchmark module against the assembled environment. MODULE names a module of
# dhis2w_integration.bench (backend, bridge, general, mcp, router, round, matrix, composite,
# longcontext, claude_general, claude_mcp, claude_bridge); ARGS are the model keys it takes.
bench: sync
	@test -n "$(MODULE)" || { echo "usage: make bench MODULE=<module> [ARGS=\"<model> ...\"]"; exit 2; }
	$(UV) run python -u -m dhis2w_integration.bench.$(MODULE) $(ARGS)

# Lint, format-check and type-check this repository's own sources.
lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy src scripts tests
	$(UV) run pyright src scripts

# Remove the cloned packs, the environment, and everything a run leaves behind.
clean:
	rm -rf checkouts .venv .pytest_cache .ruff_cache reports
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
