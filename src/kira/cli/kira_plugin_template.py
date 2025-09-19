"""Utilities for scaffolding built-in plugins and tests."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Iterable, Sequence

import click

TEMPLATE_TEST_CONTENT = dedent(
    '''
    """Basic tests for the generated plugin."""
    from __future__ import annotations

    from kira.plugin_sdk.context import PluginContext

    from {package}.plugin import activate


    def test_activate_returns_status() -> None:
        context = PluginContext(config={})
        result = activate(context)
        assert result["status"] == "ok"
    '''
)


@dataclass(frozen=True)
class PluginTemplateOptions:
    """Options for plugin scaffolding."""

    slug: str
    display_name: str
    description: str
    publisher: str
    permissions: Sequence[str]
    capabilities: Sequence[str]
    events: Sequence[str]
    commands: Sequence[str]
    output_dir: Path
    force: bool = False

    @property
    def package_name(self) -> str:
        return f"kira_plugin_{self.slug.replace('-', '_')}"

    @property
    def plugin_name(self) -> str:
        return f"kira-{self.slug}"


def slugify(name: str) -> str:
    """Convert an arbitrary name into a valid plugin slug."""
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        raise ValueError("Plugin name must contain alphanumeric characters")
    return slug


def build_manifest(options: PluginTemplateOptions) -> dict:
    """Create the default manifest payload."""
    return {
        "name": options.plugin_name,
        "version": "0.1.0",
        "displayName": options.display_name,
        "description": options.description,
        "publisher": options.publisher,
        "engines": {"kira": "^1.0.0"},
        "permissions": list(options.permissions),
        "entry": f"{options.package_name}.plugin:activate",
        "capabilities": list(options.capabilities),
        "contributes": {
            "events": list(options.events),
            "commands": list(options.commands),
        },
        "sandbox": {"strategy": "subprocess", "timeoutMs": 20000},
    }


def write_file(path: Path, content: str) -> None:
    """Write file content ensuring the parent directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def create_plugin_scaffold(options: PluginTemplateOptions) -> Path:
    """Generate the plugin scaffold on disk."""
    plugin_root = options.output_dir / options.slug
    if plugin_root.exists() and not options.force:
        raise FileExistsError(f"Plugin directory '{plugin_root}' already exists")

    package_dir = plugin_root / "src" / options.package_name
    manifest_path = plugin_root / "kira-plugin.json"
    plugin_path = package_dir / "plugin.py"
    init_path = package_dir / "__init__.py"
    test_path = Path("tests") / "plugins" / options.slug / "test_plugin.py"

    manifest = build_manifest(options)
    write_file(manifest_path, json.dumps(manifest, indent=2))

    init_lines = [
        f"{options.display_name} plugin package.",
        "",
        "from .plugin import activate",
        "",
        "__all__ = [\"activate\"]",
    ]
    write_file(init_path, "\n".join(init_lines))

    plugin_lines = [
        f"Entry point for the built-in {options.display_name} plugin.",
        "",
        "from __future__ import annotations",
        "",
        "from typing import Dict",
        "",
        "from kira.plugin_sdk.context import PluginContext",
        "",
        "",
        "def activate(context: PluginContext) -> Dict[str, str]:",
        f'    """Activate the {options.display_name.lower()} plugin."""',
        f'    context.logger.info("Activating {options.plugin_name} plugin")',
        "    context.events.publish(",
        f'        "{options.slug}.activate",',
        f'        {{"message": "{options.display_name} plugin activated", "plugin": "{options.plugin_name}"}}',
        "    )",
        f'    return {{"status": "ok", "plugin": "{options.plugin_name}"}}',
    ]
    write_file(plugin_path, "\n".join(plugin_lines))

    template = TEMPLATE_TEST_CONTENT.replace("{package}", options.package_name)
    write_file(test_path, template)

    return plugin_root


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Scaffold built-in plugin structures",
)
def cli() -> None:
    """Root command for plugin scaffolding utilities."""


@cli.command("create")
@click.argument("name")
@click.option(
    "display_name",
    "--display-name",
    help="Human readable plugin name (defaults to title-cased slug)",
)
@click.option(
    "description",
    "--description",
    default="New Kira plugin scaffold",
    show_default=True,
    help="Short plugin description",
)
@click.option(
    "publisher",
    "--publisher",
    default="kira",
    show_default=True,
    help="Plugin publisher",
)
@click.option(
    "permissions",
    "--permissions",
    multiple=True,
    default=("events.publish",),
    show_default=True,
    help="Permissions requested by the plugin",
)
@click.option(
    "capabilities",
    "--capabilities",
    multiple=True,
    default=("pull",),
    show_default=True,
    help="Capabilities exposed by the plugin",
)
@click.option(
    "events",
    "--events",
    multiple=True,
    default=("plugin.started",),
    show_default=True,
    help="Events contributed by the plugin",
)
@click.option(
    "commands",
    "--commands",
    multiple=True,
    default=("plugin.run",),
    show_default=True,
    help="Commands contributed by the plugin",
)
@click.option(
    "output_dir",
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("src/kira/plugins"),
    show_default=True,
    help="Target directory for the plugin",
)
@click.option(
    "force",
    "--force",
    is_flag=True,
    help="Overwrite existing plugin directory if it exists",
)
def create_command(
    name: str,
    display_name: str | None,
    description: str,
    publisher: str,
    permissions: tuple[str, ...],
    capabilities: tuple[str, ...],
    events: tuple[str, ...],
    commands: tuple[str, ...],
    output_dir: Path,
    force: bool,
) -> int:
    """Create a new plugin scaffold."""

    try:
        slug = slugify(name)
        options = PluginTemplateOptions(
            slug=slug,
            display_name=display_name or slug.replace("-", " ").title(),
            description=description,
            publisher=publisher,
            permissions=list(permissions),
            capabilities=list(capabilities),
            events=list(events),
            commands=list(commands),
            output_dir=output_dir,
            force=force,
        )
        create_plugin_scaffold(options)
        click.echo(
            f"✅ Created plugin scaffold for {options.plugin_name} "
            f"at {options.output_dir / slug}"
        )
        return 0
    except Exception as exc:  # pragma: no cover - exercised via tests
        click.echo(f"❌ Failed to create plugin scaffold: {exc}")
        return 1


def main(argv: Iterable[str] | None = None) -> int:
    """Entry point for ``kira plugin`` CLI operations."""

    try:
        return cli.main(args=list(argv) if argv is not None else None, standalone_mode=False)
    except SystemExit as exc:  # pragma: no cover - click normalises exit codes
        return int(exc.code) if exc.code is not None else 0


__all__ = [
    "PluginTemplateOptions",
    "build_manifest",
    "cli",
    "create_plugin_scaffold",
    "main",
    "slugify",
]
