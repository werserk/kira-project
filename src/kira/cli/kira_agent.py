"""CLI command to start Kira agent service.

Usage:
    poetry run python -m kira.cli agent start
    poetry run python -m kira.cli agent version
"""

import click

from ..agent.config import AgentConfig
from ..agent.service import create_agent_app


@click.group()
def agent() -> None:
    """Kira agent commands."""
    pass


@agent.command()
@click.option("--host", default=None, help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
def start(host: str | None, port: int | None) -> None:
    """Start agent HTTP service."""
    try:
        import uvicorn
    except ImportError:
        click.echo("Error: uvicorn not installed. Install with: poetry install --extras agent", err=True)
        return

    config = AgentConfig.from_env()

    if host:
        config.host = host
    if port:
        config.port = port

    click.echo(f"Starting Kira Agent on {config.host}:{config.port}...")
    click.echo(f"LLM Provider: {config.llm_provider}")

    app = create_agent_app(config)
    uvicorn.run(app, host=config.host, port=config.port)


@agent.command()
def version() -> None:
    """Show agent version."""
    click.echo("Kira Agent v0.1.0 (Sprint 1)")
    click.echo("Status: Alpha")


if __name__ == "__main__":
    agent()
