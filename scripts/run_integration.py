"""The integration runner: assemble the dhis2w ecosystem and run everyone together.

Reading ecosystem.yaml, this clones each pack repository at its tracked ref into checkouts/,
installs it editable into the current environment, and then, against the one environment where
the host surfaces and every pack are installed side by side, it runs each pack's own suite and
this repository's own tests. It reports one green or red.

A pack whose checkout is already present is moved to its ref's tip; one with local changes is
left where it is, which is what lets a local, offline verification substitute a copy of a
sibling working tree for a clone.

It is generic over the manifest: it iterates the components the manifest gives `role: pack` and
carries no knowledge of any particular pack.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
import yaml
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ecosystem.yaml"
CHECKOUTS = ROOT / "checkouts"
INTEGRATION_TESTS = ROOT / "tests"

application = typer.Typer(add_completion=False, help="Assemble and run the dhis2w ecosystem.")


class Component(BaseModel):
    """One component of the ecosystem: its repository, the ref it tracks, and the role it plays."""

    model_config = ConfigDict(frozen=True)

    name: str
    repo: str
    ref: str
    role: str

    @property
    def checkout_path(self) -> Path:
        """Where this component is cloned, under checkouts/."""
        return CHECKOUTS / self.name

    @property
    def makefile_path(self) -> Path:
        """The Makefile inside the checkout, which drives the component's own suite when present."""
        return self.checkout_path / "Makefile"

    @property
    def tests_path(self) -> Path:
        """The component's own test directory inside its checkout."""
        return self.checkout_path / "tests"


class Manifest(BaseModel):
    """Everything ecosystem.yaml names, in the order it names it."""

    model_config = ConfigDict(frozen=True)

    components: tuple[Component, ...]

    def with_role(self, role: str) -> tuple[Component, ...]:
        """The components in one role, in manifest order."""
        return tuple(component for component in self.components if component.role == role)


class ComponentEntry(BaseModel):
    """One manifest entry, before its name is folded in from the mapping key."""

    model_config = ConfigDict(frozen=True)

    repo: str
    ref: str
    role: str


class StepResult(BaseModel):
    """Whether one named step of the run passed."""

    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool


def read_manifest() -> Manifest:
    """Parse ecosystem.yaml into the typed manifest."""
    document = yaml.safe_load(MANIFEST.read_text())
    entries = {name: ComponentEntry.model_validate(entry) for name, entry in document["components"].items()}
    return Manifest(
        components=tuple(
            Component(name=name, repo=entry.repo, ref=entry.ref, role=entry.role) for name, entry in entries.items()
        )
    )


def clone(component: Component) -> None:
    """Clone a component at its ref, or bring a checkout that is already there up to that ref.

    A pack's source is installed from the ref's tip, so its tests must be read from the same tip:
    a checkout left at an older commit runs one commit's tests against another's code. A checkout
    with local changes is left alone and reported, never reset.
    """
    if component.checkout_path.exists():
        dirty = subprocess.run(
            ["git", "-C", str(component.checkout_path), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if dirty:
            typer.echo(f"  keep    {component.name}  (checkout has local changes; not moved to {component.ref})")
            return
        typer.echo(f"  refresh {component.name}  {component.repo}@{component.ref}")
        subprocess.run(
            ["git", "-C", str(component.checkout_path), "fetch", "--depth", "1", "origin", component.ref], check=True
        )
        subprocess.run(["git", "-C", str(component.checkout_path), "reset", "--hard", "FETCH_HEAD"], check=True)
        return
    CHECKOUTS.mkdir(exist_ok=True)
    typer.echo(f"  clone   {component.name}  {component.repo}@{component.ref}")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", component.ref, component.repo, str(component.checkout_path)],
        check=True,
    )


def install(component: Component) -> None:
    """Install a cloned pack editable into the assembled environment, so its plugin is discovered.

    `--no-deps` keeps the pack from pulling a published host over the one already installed here:
    the assembled environment is the ecosystem, and a pack's own pins must not reshape it.
    """
    typer.echo(f"  install {component.name}  (editable, --no-deps)")
    subprocess.run(["uv", "pip", "install", "--no-deps", "-e", str(component.checkout_path)], check=True)


def run_component_suite(component: Component) -> StepResult:
    """Run one pack's own suite inside its checkout: its `make test` when it has one, else pytest."""
    typer.echo(f"\n=== suite: {component.name} ===")
    if component.makefile_path.exists():
        completed = subprocess.run(["make", "test"], cwd=component.checkout_path)
        return StepResult(name=f"{component.name} suite", passed=completed.returncode == 0)
    if not component.tests_path.is_dir():
        typer.echo(f"  skip    {component.name}: no Makefile and no tests/ directory")
        return StepResult(name=f"{component.name} suite", passed=True)
    completed = subprocess.run([sys.executable, "-m", "pytest", "tests"], cwd=component.checkout_path)
    return StepResult(name=f"{component.name} suite", passed=completed.returncode == 0)


def run_integration_tests() -> StepResult:
    """Run this repository's own tests against the assembled environment."""
    typer.echo("\n=== pytest: dhis2w-integration ===")
    completed = subprocess.run([sys.executable, "-m", "pytest", str(INTEGRATION_TESTS)], cwd=ROOT)
    return StepResult(name="integration tests", passed=completed.returncode == 0)


def report(results: list[StepResult]) -> int:
    """Print the summary and return the shell exit code the whole run earned."""
    typer.echo("\n=== integration summary ===")
    for result in results:
        typer.echo(f"  {'PASS' if result.passed else 'FAIL'}  {result.name}")
    every = all(result.passed for result in results)
    typer.echo(f"\n{'GREEN: the ecosystem is coherent.' if every else 'RED: something above failed.'}")
    return 0 if every else 1


@application.command()
def main(
    clone_only: bool = typer.Option(
        False, "--clone-only", help="Clone every pack named in the manifest, install none, and stop."
    ),
) -> None:
    """Clone every pack, install it into this environment, run its suite, then run ours."""
    manifest = read_manifest()
    packs = manifest.with_role("pack")

    typer.echo("=== assemble: clone the packs named in ecosystem.yaml ===")
    for pack in packs:
        clone(pack)
    if clone_only:
        raise typer.Exit(0)

    for pack in packs:
        install(pack)

    results = [run_component_suite(pack) for pack in packs]
    results.append(run_integration_tests())
    raise typer.Exit(report(results))


if __name__ == "__main__":
    application()
