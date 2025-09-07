"""
Venus CLI entry point.
This module serves as the command-line interface (CLI) for the Venus assistant.
It allows users to interact with the assistant through various commands.
"""

import importlib
import os
import sys
from typing import Any, cast

import click
import logfire
import uvicorn
from fasta2a import FastA2A

from .agent import Venus
from .constants import serve_command, server_config
from .logger import VenusConsole
from .mcp_server import MCP

vc = VenusConsole()

sys.path.insert(0, os.getcwd())


def attr_resolve(obj: Any, path: str):
    """
    Safely access nested attributes of an object using a dot-separated string path.

    Args:
        obj: The object to access.
        path (str): The dot-separated string path to the attribute.
    """
    for attr in path.split("."):
        try:
            obj = getattr(obj, attr)
        except AttributeError:
            raise AttributeError(
                f"{type(obj).__name__} object has no attribute '{attr}'"
            )
    return obj


def start_chat(app: Venus, deps: None = None, prog_name: str | None = None):
    """
    Start the chat interface.
    """
    prog_name = prog_name or app.name or "venus"
    app.to_cli_sync(deps=deps, prog_name=prog_name)


@click.group()
def main():
    """
    Entry point for the Venus CLI.
    This function initializes and starts the command-line interface.
    """
    pass


@main.command()
def version():
    """Display the current version of Venus."""
    from . import __version__

    vc.info(f"Venus version: {__version__}")


@main.command()
@click.argument("app_string")
@click.option("--name", default="venus", help="Name of the chat assistant")
def chat(app_string: str, name: str):
    """Start the chat interface."""
    try:
        module_name, app_name = app_string.split(":", maxsplit=1)
        module = importlib.import_module(module_name)

        if "." in app_name:
            base_name, app_name = app_name.split(".", maxsplit=1)
            app = getattr(module, base_name)
            app = attr_resolve(app, app_name)
        else:
            app = getattr(module, app_name)

        start_chat(app, prog_name=name)

    except ValueError:
        vc.print_exception(show_locals=True)
        vc.warn("Invalid format. Use 'module:app' for the chat command.")

    except ModuleNotFoundError:
        vc.warn(f"Module '{module_name}' not found.")

    except AttributeError:
        vc.print_exception(show_locals=True)
        vc.warn(f"App '{app_name}' not found in module '{module_name}'.")


@main.command()
@click.option(
    "--path",
    required=True,
    help="Include MCP tools from module, use comma for multiple paths",
)
@click.option("--name", default="Venus CLI", help="Name of the MCP server")
@click.option("--all", is_flag=True, help="Tool type to include from specified module")
@click.option("--host", default="127.0.0.1", help="Host to serve MCP")
@click.option("--port", default=8000, help="Port to serve MCP")
@click.option(
    "--configure", is_flag=True, help="Configure Claude with Current MCP Settings"
)
@click.option(
    "--transport",
    default="sse",
    help="Transport type of MCP Server",
    type=click.Choice(["sse", "http", "streamable-http"]),
)
def mcp(
    all: bool,
    host: str,
    name: str,
    path: str,
    port: int,
    transport: str,
    configure: bool,
):
    if transport == "stdio":
        return vc.info(
            "Stdio transport is not supported in the CLI. Use 'sse' or 'http' instead.",
            color="red",
            bold=True,
        )

    vc.info("MCP tools will be loaded from specified modules.")

    if all:
        config_dict = {"load_all": True}
    else:
        config_dict = {}

    mcp = MCP(name=name, host=host, port=port)
    vc.info(
        f"Initiating {name} MCP Server with {transport.upper()} transport at http://{host}:{port}"
    )

    if transport == "http":
        transport = "streamable-http"

    try:
        modules = [module.removesuffix(".py") for module in path.strip().split(",")]
        mcp.configure(
            modules=modules,
            transport=transport,
            configure_claude=configure,
            **config_dict,
        )
    except:
        vc.print_exception(show_locals=True, max_frames=2)
        return vc.fail("An error occured during MCP configuration.")

    vc.info("Listing MCP tools:", color="blue")
    names = [name for name, _ in mcp.mcp_tools.items()]
    names.sort(key=lambda x: x)
    for i, name in enumerate(names):
        vc.info(f"✔ [{i + 1}] Tool `{name}` registered!", color="blue", bold=False)

    vc.info("Running MCP Server...")
    mcp.run()


@main.command()
@click.argument("app")
@click.argument("plugin", required=False)
@click.option("--host", default=None, help="Host to serve on")
@click.option("--port", default=None, help="Port to serve on")
@click.option("--auto", is_flag=True, help="Automatically setup tools HTTP API")
@click.option("--env", default="dev", help="Environment to use (default: dev)")
def serve(app: str, host: str, port: int, auto: bool, env: str, plugin: str = None):
    """Serve the Venus application."""
    if env not in ["dev", "prod"]:
        vc.fail(f"Invalid environment '{env}'. Use 'dev' or 'prod'.")
        return

    host = host or server_config["host"][env]
    port = int(port or server_config["port"][env])

    try:
        module, app = app.split(":")
        app = app.removesuffix(".api")
        module_instance = importlib.import_module(module)
        app_instance = attr_resolve(module_instance, app)

        if plugin == "a2a":
            module_contents = dir(module_instance)
            a2a_app = next(
                filter(
                    lambda x: isinstance(getattr(module_instance, x), FastA2A),
                    module_contents,
                ),
                None,
            )

            if a2a_app is None:
                vc.warn(f"No FastA2A app found in module '{module}'.")
                vc.info("Serving default A2A app!")
                asgi_app = cast(FastA2A, app_instance.to_a2a())
            else:
                vc.info(f"Using existing A2A app at {module}:{a2a_app}")
                asgi_app = cast(FastA2A, getattr(module_instance, a2a_app))

            vc.info(
                f"Serving [bold green]Venus A2A API[/bold green] at [cyan]http://{host}:{port}[/cyan]"
            )
            return uvicorn.run(asgi_app, host=host, port=port)

        if not hasattr(app_instance.api, "tools_http_api"):
            if auto:
                app_instance.tools_http_api()

                vc.info(
                    f"Serving [bold green]Venus Toolchain API[/bold green] "
                    f"with [cyan]{len(app_instance.tools)}[/cyan] tools."
                )
                vc.info(
                    f"[bold blue]Serving at:[/bold blue] "
                    f"[link]http://{host}:{port}[/link]"
                )

                uvicorn.run(app=app_instance.api, host=host, port=port)
                return

            vc.fail(
                "[cyan]App.tools_http_api()[/cyan] "
                "[bold yellow]not called yet.[/bold yellow]\n"
                "[bold green]Hint:[/bold green]     Pass [italic]--auto[/italic] to use registered tools of Agent automatically."
            )
            return

        os.system(serve_command.format(module=module, app=app, host=host, port=port))

    except ValueError:
        vc.warn("Invalid format. Use 'module:app' for the serve command.")


if __name__ == "__main__":
    main()
