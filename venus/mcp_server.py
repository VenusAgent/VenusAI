"""
Utility module for Model Context Protocol (MCP) Server
"""

import inspect
import json
import sys
from pathlib import Path
from typing import Literal

from mcp.server import FastMCP

from . import settings
from ._module_utils import fetch_module_tools


class MCP(FastMCP):
    """
    MCP (Model Context Protocol) server class that extends FastMCP.

    This class is used to create an MCP server that can handle multiple contexts.
    It provides methods to add tools and manage the server.
    """

    transport_type: str | None = None

    @property
    def mcp_tools(self):
        """
        Get the list of tools available in the MCP server.

        Returns:
            List of tools.
        """
        return self._tool_manager._tools

    def configure(
        self,
        modules: str | list[str] = [],
        load_all: bool = False,
        mcp_tool: bool = True,
        force_ssl: bool = False,
        transport: Literal["stdio", "sse"] = "stdio",
        stream_url: str | None = None,
        configure_claude: bool = False,
        ignore_project: bool = True,
        mcp_remote_transport: Literal[
            "http-first", "http-only", "sse-first", "sse-only"
        ] = None,
    ) -> None:
        """
        Build the MCP server for the agent.

        This method initializes the MCP server with the agent's tools and starts serving.

        Args:
            modules (str | list[str]): The module or list of modules to load tools from.
            load_all (bool): Whether to load all functions from the modules as tools.
            mcp_tool (bool): Whether to consider only functions decorated with @mcp_tool.
            force_ssl (bool): Whether to force SSL for the server.
            transport (str): The transport method to use. Default is 'stdio'.
            stream_url (str | None): The URL for streaming, if applicable.
            configure_claude (bool): Whether to configure Claude integration.
            ignore_project (bool): Whether to ignore the current project when configuring Claude.
            mcp_remote_transport (str | None): The transport method for MCP remote ('http-first', 'http-only', 'sse-first', 'sse-only').
        """
        _mcp_tools = fetch_module_tools(modules, mcp_tool=mcp_tool, load_all=load_all)
        self.transport_type = transport

        for fn in _mcp_tools:
            if fn.__name__ in self.mcp_tools:
                continue

            self.add_tool(
                fn=fn,
                name=fn.__name__,
                title=fn.__name__.replace("_", " ").title(),
                description=fn.__doc__,
            )

        if configure_claude and (frame := inspect.currentframe()) and frame.f_back:
            traceback = inspect.getframeinfo(frame.f_back)
            claude_path = Path(settings.default_claude_path)
            caller_path = Path(traceback.filename)
            caller_file = caller_path.name
            route = "sse" if transport == "sse" else "mcp"
            base_url = f"http{'s' if force_ssl else ''}://{self.settings.host}:{self.settings.port}"
            stream_url = stream_url or f"{base_url}/{route}"
            if transport == "stdio":
                data = {
                    "mcpServers": {
                        self.name
                        or "venus": {
                            "command": Path(sys.executable).name,
                            "args": [
                                "-m",
                                "uv",
                                "--directory",
                                str(caller_path.parent),
                                "run",
                                "--no-project" if ignore_project else "",
                                caller_file,
                            ],
                        }
                    }
                }
            elif transport == "sse":
                data = {
                    "mcpServers": {
                        self.name
                        or "venus": {
                            "command": "npx",
                            "args": [
                                "-y",
                                "mcp-remote",
                                stream_url,
                                "--allow-http" if not force_ssl else "",
                            ],
                        }
                    }
                }
            elif transport == "streamable-http":
                data = {
                    "mcpServers": {
                        self.name
                        or "venus": {
                            "command": "npx",
                            "args": [
                                "-y",
                                "mcp-remote",
                                stream_url,
                                "--allow-http" if not force_ssl else "",
                                "--transport",
                                (
                                    "http-only"
                                    if not mcp_remote_transport
                                    else mcp_remote_transport
                                ),
                            ],
                        }
                    }
                }
            else:
                raise ValueError(
                    f"Invalid transport {transport!r}. Did you mean stdio, sse or streamable-http?"
                )

            if not claude_path.parent.exists():
                raise FileNotFoundError(
                    f"Claude Path {str(claude_path)!r} was invalid. "
                    "Check the file path or create it."
                )

            claude_config = json.dumps(data, indent=2, ensure_ascii=False)
            claude_path.touch(exist_ok=True)
            claude_path.write_text(claude_config)

    def run(
        self,
        transport: Literal["stdio", "sse", "streamable-http"] = None,
        mount_path: str | None = None,
    ) -> None:
        """
        Run the MCP server.

        Args:
            transport (str): The transport method to use. Default is 'stdio'.
        """
        transport = transport or self.transport_type or "stdio"
        super().run(transport=transport, mount_path=mount_path)
