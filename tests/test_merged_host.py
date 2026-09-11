"""The assembled plugin host is coherent: every pack loads beside the built-ins and composes.

These are the integration's own tests. They assert the property no single repository can: that
the host's built-in plugins, the surfaces shipped in the host workspace, and every out-of-repo
pack load into one `PluginHost` per version tree, mount onto one Typer application without a
command-group collision, and register onto one FastMCP server without a tool-name collision.
"""

from __future__ import annotations

from collections import Counter

import pytest
import typer
from dhis2w_core.plugin import PluginHost, load_plugin_host
from fastmcp import FastMCP

#: Every plugin tree the host supports. A pack that binds only some of them shows up here.
VERSION_KEYS = ["v41", "v42", "v43"]

#: The contributions that must be present in every tree: a built-in, the FHIR surface shipped in
#: the host workspace, and the out-of-repo pack.
EXPECTED_NAMES = ["metadata", "fhir", "security"]

# `security` is contributed twice in this environment: dhis2w-core still ships a built-in
# security plugin, and dhis2w-security contributes the same name from its own repository. The
# pack supersedes the built-in, which leaves dhis2w-core in the follow-up to
# winterop-com/dhis2w#790 (the branch that put the plugin host on pluginkit). Until that lands,
# it is the one duplicate the assembled host is allowed to carry.
KNOWN_DUPLICATE_NAMES = {"security"}


@pytest.fixture(scope="session", params=VERSION_KEYS)
def host(request: pytest.FixtureRequest) -> PluginHost:
    """The assembled plugin host for one version tree, built once per tree."""
    return load_plugin_host(request.param)


def test_every_expected_contribution_is_in_the_assembled_host(host: PluginHost) -> None:
    for name in EXPECTED_NAMES:
        assert host.get(name) is not None, f"{name} is missing from the {host.version_key} host: {host.names}"


def test_the_assembled_host_contributes_more_than_the_built_ins(host: PluginHost) -> None:
    assert len(host.contributions) > len(EXPECTED_NAMES), "the assembled host loaded fewer plugins than there are packs"


def test_no_plugin_failed_to_load(host: PluginHost) -> None:
    assert host.failures == (), f"{host.version_key}: " + "; ".join(
        f"{failure.name}: {failure.error}" for failure in host.failures
    )


def test_the_contribution_names_are_unique(host: PluginHost) -> None:
    duplicated = {name for name, count in Counter(host.names).items() if count > 1}
    assert duplicated <= KNOWN_DUPLICATE_NAMES, f"{host.version_key} contributes {duplicated} more than once"


def test_every_contribution_mounts_on_one_typer_application(host: PluginHost) -> None:
    application = typer.Typer()
    host.mount_cli(application)
    mounted = [
        group.name or (group.typer_instance.info.name if group.typer_instance is not None else None)
        for group in application.registered_groups
    ]
    mounted += [command.name for command in application.registered_commands]
    assert mounted, f"{host.version_key} mounted no command group at all"
    duplicated = {name for name, count in Counter(mounted).items() if count > 1}
    assert duplicated <= KNOWN_DUPLICATE_NAMES, f"{host.version_key} mounts the {duplicated} command group twice"


async def test_every_contribution_registers_on_one_mcp_server(host: PluginHost) -> None:
    """A tool name claimed by two contributions is a collision; the last registration would win."""
    owners: dict[str, list[str]] = {}
    for contribution in host.contributions:
        server: FastMCP[None] = FastMCP(name=f"{host.version_key}-{contribution.name}")
        contribution.register_mcp(server)
        for tool in await server.list_tools():
            owners.setdefault(tool.name, []).append(contribution.name)
    assert owners, f"{host.version_key} registered no MCP tool at all"
    collisions = {name: claimants for name, claimants in owners.items() if len(claimants) > 1}
    unexpected = {name for name, claimants in collisions.items() if not set(claimants) <= KNOWN_DUPLICATE_NAMES}
    assert not unexpected, f"{host.version_key} registers {sorted(unexpected)} from more than one contribution"
