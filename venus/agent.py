import asyncio
import inspect
import json
import logging
import os
import types
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import (Any, Callable, Dict, Generic, Literal, Optional, Sequence,
                    TypeVar, Union, cast, get_type_hints, overload)

import tinydb
import uvicorn
from dotenv import load_dotenv
from fastapi import APIRouter as Router
from fastapi import FastAPI as Server

from pydantic_ai import Agent, EndStrategy
from pydantic_ai import _system_prompt as _system_prompt
from pydantic_ai._agent_graph import HistoryProcessor
from pydantic_ai._run_context import AgentDepsT
from pydantic_ai.agent import InstrumentationSettings
from pydantic_ai.agent.abstract import EventStreamHandler
from pydantic_ai.builtin_tools import AbstractBuiltinTool
from pydantic_ai.mcp import MCPServer
from pydantic_ai.models import KnownModelName
from pydantic_ai.models.openai import Model
from pydantic_ai.output import OutputDataT, OutputSpec
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import (Tool, ToolFuncContext, ToolFuncEither,
                               ToolFuncPlain, ToolParams)
from pydantic_ai.toolsets import AbstractToolset, ToolsetFunc

from . import decorators
from ._decorator_utils import extract_function_body, has_context_param
from ._module_utils import import_module
from .decorators import is_context_tool, safe_call
from .errors import (ErrorDict, ExecutionNotAllowed, InvalidContextParam,
                     InvalidFunction, InvalidTool, InvalidTools)
from .helpers import time_diff_prettify, tools
from .logger import VenusConsole
from .permissions import Permissions, get_allowed_tools
from .prompts import CODING_PROMPT
from .schemas import DoesNeedFix, FixFuncResult
from .settings import Settings
from .types import Deps, FuncParams, ToolsPrepareFunc, _EnableFeature

"""
Agent module for building and configuring an agent with HTTP client support.
"""

ToolName = str
T = TypeVar("T")
NoneType = type(None)

vc = VenusConsole()
settings = Settings()

httpx_logger = logging.getLogger("httpx")
httpx_logger.disabled = True


class Venus(Agent, Generic[AgentDepsT, OutputDataT]):  # pyright: ignore
    """
    Venus is a subclass of Agent that integrates with the Venus framework.
    It provides methods for registering tools, building the agent, and integrating tools from a specified module.

    Attributes:
        load_env (bool): Whether to load environment variables from a .env file.
        override_env (bool): Whether to override existing environment variables.
        tool_modules (str | list[str] | None): The module(s) from which to integrate tools.
        warnings (bool): Whether to show warnings.
        **options: Another keyword arguments to pass into original Agent class.
    """

    @overload
    def __init__(  # pyright: ignore
        self,
        # parameters of both as common below
        model: Model | KnownModelName | str | None = None,
        *,
        # parameters of venus.Venus below
        fix_model: str | Model | None = None,
        load_env: bool = True,
        override_env: bool = False,
        tool_modules: str | list[str] | None = None,
        warnings: bool = True,
        # parameters of pydantic_ai.Agent below
        output_type: OutputSpec[OutputDataT] = str,
        instructions: (
            str
            | _system_prompt.SystemPromptFunc[AgentDepsT]
            | Sequence[str | _system_prompt.SystemPromptFunc[AgentDepsT]]
            | None
        ) = None,
        system_prompt: str | Sequence[str] = (),
        deps_type: type[AgentDepsT] = NoneType,
        name: str | None = None,
        model_settings: ModelSettings | None = None,
        retries: int = 1,
        output_retries: int | None = None,
        tools: Sequence[Tool[AgentDepsT] | ToolFuncEither[AgentDepsT, ...]] = (),
        builtin_tools: Sequence[AbstractBuiltinTool] = (),
        prepare_tools: ToolsPrepareFunc[AgentDepsT] | None = None,
        prepare_output_tools: ToolsPrepareFunc[AgentDepsT] | None = None,
        toolsets: (
            Sequence[AbstractToolset[AgentDepsT] | ToolsetFunc[AgentDepsT]] | None
        ) = None,
        mcp_servers: Sequence[MCPServer] = (),
        defer_model_check: bool = False,
        end_strategy: EndStrategy = "early",
        instrument: InstrumentationSettings | bool | None = None,
        history_processors: Sequence[HistoryProcessor[AgentDepsT]] | None = None,
        event_stream_handler: EventStreamHandler[AgentDepsT] | None = None,
    ) -> None:
        # Overload for highlighting the original Agent constructor signature.
        pass

    def __init__(
        self,
        # positional arguments
        model: Model | KnownModelName | None = None,
        name: str | None = None,
        *,
        # keyword arguments
        fix_model: Model | KnownModelName | None = None,
        load_env: bool = True,
        override_env: bool = False,
        tool_modules: str | list[str] | None = None,
        system_prompt: str | Sequence[str] = (),
        warnings: bool = True,
        **options,
    ):
        if warnings and options.get("mcp_servers"):
            vc.log(
                "Warning: `mcp_servers` parameter is deprecated, "
                "use `toolsets` parameter instead",
                color="yellow",
                bold=True,
                level_color="yellow",
            )

        self._agent_built = False
        self.build_agent(
            model=model,
            load_env=load_env,
            override_env=override_env,
            system_prompt=system_prompt,
            name=name or settings.agent_name,
            **options,
        )
        self.logger = VenusConsole()
        self.warnings = warnings
        self.fix_model = fix_model or settings.fix_model or model

        self._tool_modules = tool_modules
        self._tools = self.integrate_tools()
        self._handlers = defaultdict(dict)
        self._api = Server(title="Venus Toolchain API", version="1.0.0")
        self._router = Router(tags=["Venus Toolchain API"])
        self._api.serve = self.serve

        async def homepage():
            """Venus Toolchain API Homepage"""
            return {
                "title": "Venus Toolchain API",
                "version": "1.0.0",
                "docs": self._api.docs_url,
                "redoc": self._api.redoc_url,
                "openapi": self._api.openapi_url,
            }

        self._router.add_api_route(
            path="/",
            endpoint=homepage,
            operation_id="homepage",
        )

    def __enter__(self):  # TODO: Maybe deprecate sync context managers
        """
        Enter the Venus agent context.

        This method is called when entering the context manager.
        It initializes the agent and prepares it for use.

        #### Reach the agent and invoke the run method.
        >>> with Venus() as agent:
                agent.ask('What is the capital of Turkiye?')
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[types.TracebackType],
    ):
        """
        Exit the Venus agent context and clean up resources.

        This method is called when exiting the context manager.
        It cleans up resources and closes the HTTP client.
        """
        if exc_type is not None:
            vc.print_exception(show_locals=True, max_frames=2)

        self.cleanup()

    async def __aenter__(self):
        """
        Asynchronously enter the Venus agent context.

        This method is called when entering the context manager in an asynchronous context.
        It initializes the agent and prepares it for use.

        #### Reach the agent and invoke the run method.
        >>> async with Venus() as agent:
                await agent.run('What is the capital of Turkiye?')
        """
        return await super().__aenter__()

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[types.TracebackType],
    ):
        """
        Asynchronously exit the Venus agent context and clean up resources.

        This method is called when exiting the context manager in an asynchronous context.
        It cleans up resources and closes the HTTP client.
        """
        if exc_type is not None:
            vc.print_exception(show_locals=True, max_frames=2)

        self.cleanup()

        return await super().__aexit__(exc_type, exc_value, traceback)

    def cleanup(self) -> None:
        """
        Clean up resources used by the Venus agent.

        This method is called to clean up resources used by the agent.
        It closes the fix and cache databases.
        """
        try:
            self.fixdb.close()
        except Exception as e:
            vc.print_exception(show_locals=True, max_frames=2)
            vc.fail(f"Failed to close fix database caused by: {e()}")

        try:
            self.cachedb.close()
        except Exception as e:
            vc.print_exception(show_locals=True, max_frames=2)
            vc.fail(f"Failed to close cache database caused by: {e()}")

    @property
    def ask(self):
        """
        Get the synchronous run method of the agent.
        This property allows you to use the agent's run method synchronously.
        """
        return self.run_sync

    @overload
    def add_tool(self, tool: Tool[AgentDepsT] | None = None) -> Tool[AgentDepsT] | None:
        """
        Register a tool with the agent.

        Do not use tool parameter if you don't have a `Tool` instance.

        Args:
            tool (Tool): The tool to register.
        """
        pass

    @overload
    def add_tool(
        self,
        function: Callable[FuncParams, T] | None = None,
        name: str | None = None,
        description: str | None = None,
        takes_ctx: bool = False,
        **tool_options,
    ) -> Tool[AgentDepsT] | None:
        """
        Register a tool with the agent.

        Do not use tool parameter if you don't have a `Tool` instance.

        Args:
            function (Callable): The function to register as a tool.
            name (str): The name of the tool.
            description (str): The description of the tool.
            takes_ctx (bool): Whether the function takes RunContext as an argument.
            **tool_options: Additional options for the tool.
        """
        pass

    @overload
    def add_tool(
        self,
        function: Callable[ToolParams, T],
        json_schema: str | dict,
        /,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Tool[AgentDepsT] | None:
        """
        Register a tool with the agent using a JSON schema.

        Args:
            function (Callable): The function to register as a tool.
            json_schema (str | dict | BaseModel): The JSON schema for the tool.
            name (str): The name of the tool.
            description (str): The description of the tool.
        """
        pass

    def add_tool(
        self,
        tool: Tool | None = None,
        function: Callable[ToolParams, Any] | None = None,
        json_schema: str | dict | None = None,
        name: str | None = None,
        description: str | None = None,
        takes_ctx: bool = False,
        **tool_options,
    ) -> Tool[AgentDepsT] | None:
        """
        Register a tool with the agent.

        Do not use tool parameter if you don't have a `Tool` instance.
        """

        assert not json_schema or isinstance(json_schema, (str, dict)), ValueError(
            f"Expected 'json_schema' to be a str, dict, or None, got {type(json_schema).__name__!r}."
        )

        if function and tool:
            raise InvalidTool(
                "Both 'tool' and 'function' provided. Can not use both at the same time. "
                "Use 'tool' param to provide a Tool instance."
            )

        elif not function and not tool:
            raise InvalidTool("Either 'tool' or 'function' must be provided.")

        elif tool and not isinstance(tool, Tool):
            raise InvalidTool(
                f"Expected 'tool' to be an instance of Tool, got {type(tool).__name__!r}."
            )

        elif json_schema and not (name and description and function):
            raise InvalidTool(
                "If 'json_schema' is provided, 'name', 'description', and 'function' must also be provided."
            )

        if not json_schema:
            self._function_toolset.add_tool(
                Tool(
                    function=function,
                    name=name or function.__name__,
                    description=description or function.__doc__,
                    takes_ctx=takes_ctx,
                    **tool_options,
                )
            )
        elif tool:
            self._function_toolset.add_tool(tool)
        else:
            self._function_toolset.add_tool(
                Tool.from_schema(
                    function=function,
                    json_schema=(
                        json_schema
                        if isinstance(json_schema, dict)
                        else json.loads(json_schema)
                    ),
                    name=name or function.__name__,
                    description=description or function.__doc__,
                    takes_ctx=takes_ctx,
                )
            )

        if name in self.tools:
            return self.tools[name]
        return tool

    def build_agent(
        self,
        load_env: bool = True,
        override_env: bool = False,
        **options,
    ) -> None:
        """
        Build the agent with the specified configuration.

        Args:
            load_env (bool): Whether to load environment variables from a .env file.
            override_env (bool): Whether to override existing environment variables.
            **options: Additional options for the agent.
        """
        if self._agent_built:
            return vc.log(
                "Agent already built in constructor, build_agent method can not call from external context"
            )
        self._agent_built = True
        if load_env:
            load_dotenv(Path(os.getcwd()) / ".env", override=override_env)

        model = settings.model_name
        system_prompt = settings.system_prompt.format(
            name=options.get("name", settings.agent_name)
        )

        if "model" in options and options["model"]:
            model = options.pop("model")

        if "system_prompt" in options and options["system_prompt"]:
            system_prompt = options.pop("system_prompt")

        options.update({"model": model, "system_prompt": system_prompt})
        is_callable = cast(
            Callable[[Tool[AgentDepsT]], bool],
            lambda tool: cast(
                bool, callable(tool) or callable(getattr(tool, "function", None))
            ),
        )
        if not all(map(is_callable, options.get("tools", []))):
            raise InvalidTool(
                "All tools must be callable but some of the provided tools are not callable."
            )

        super().__init__(**options)

        fix_dir_parent = Path("./fixes")
        fix_caches = fix_dir_parent / ".cache"

        if not fix_caches.exists():
            fix_caches.mkdir(parents=True, exist_ok=True)

        self._fixdb = tinydb.TinyDB("./fixes/fixes.json")
        self._cachedb = tinydb.TinyDB("./fixes/.cache/invokes.json")

    @property
    def fix_agent(self) -> "VenusCode":
        """
        Get the fix agent for the Venus agent.

        Returns:
            VenusCode: The fix agent instance.
        """
        if not hasattr(self, "_fix_agent"):
            self._fix_agent = VenusCode(
                model=self.fix_model or self.model or settings.model_name,
                system_prompt=settings.default_fix_prompt,
                permission=Permissions.WRITE_APPEND,
            )
        return self._fix_agent

    @fix_agent.setter
    def fix_agent(self, agent: "VenusCode") -> None:
        """
        Set fix agent for the Agent.
        """
        self._fix_agent = agent

    @property
    def fixdb(self) -> tinydb.TinyDB:
        """
        Get the database for storing fixes.

        Returns:
            tinydb.TinyDB: The database instance for storing fixes.
        """
        return self._fixdb

    @property
    def cachedb(self) -> tinydb.TinyDB:
        """
        Get the database for storing invoke caches.

        Returns:
            tinydb.TinyDB: The database instance for storing invoke caches.
        """
        return self._cachedb

    @property
    def api(self) -> Server:
        """
        Get the Server instance for the agent.

        Returns:
            Server: The Server instance for the agent if available, otherwise None.
        """
        if not hasattr(self._api, "tools_http_api"):
            if self.warnings:
                vc.warn(
                    "[bold cyan]Default application is being served. "
                    "Tools are not exposed as HTTP APIs[/]"
                )
                vc.warn(
                    "[bold cyan]Call the `tools_http_api` method "
                    "to enable tool routes[/]"
                )
                vc.warn(
                    "[bold cyan]Note: This is an experimental feature and "
                    "recommended for local use only[/]"
                )
        return self._api

    def serve(self, host: str = "localhost", port: int = 1283) -> None:
        """
        Serve the Server application.

        Args:
            host (str): The host to bind the server to.
            port (int): The port to bind the server to.
        """
        host = host or settings.server_host
        port = port or settings.server_port

        uvicorn.run(self.api, host=host, port=port)

    @property
    def tools(self) -> Dict[str, Tool[AgentDepsT]]:
        """
        Get all the tools for the agent.

        Returns:
            dict: A dictionary of tool names and their corresponding Tool objects.
        """
        return self._function_toolset.tools

    @property
    def module_tools(self) -> Dict[str, Tool[AgentDepsT]]:
        """
        Get the tools from the module.

        Returns:
            dict: A dictionary of tool names and their corresponding Tool objects.
        """
        return self._tools

    def integrate_tools(self) -> Dict[str, Tool[AgentDepsT]]:
        """
        Integrate tools from the specified module(s) into the agent.

        This method checks if the tool_modules attribute is set and integrates tools accordingly.
        Returns:
            dict: A dictionary of tool names and their corresponding Tool objects.
        """
        if not self._tool_modules:
            return {}

        if isinstance(self._tool_modules, str):
            return self._integrate_tool(self._tool_modules)

        if isinstance(self._tool_modules, (list, tuple, set)):
            tools = {}
            for tool_module in self._tool_modules:
                tools.update(self._integrate_tool(tool_module))
            return tools

        return {}

    def _integrate_tool(self, tool_module: str) -> Dict[str, Tool[AgentDepsT]]:
        """
        Integrate tools from a specified module.

        Args:
            tool_module (str): The name of the module to integrate tools from.

        Returns:
            dict: A dictionary of tool names and their corresponding Tool objects.
        """
        valid_functions = import_module(tool_module)
        if not valid_functions:
            return {}

        module_tools = []
        for func in valid_functions:
            if func.__name__ not in self.tools:
                self.add_tool(
                    name=func.__name__,
                    function=func,
                    takes_ctx=getattr(func, "context_tool", False),
                    description=func.__doc__,
                )
                module_tools.append(func.__name__)

        return {k: v for k, v in self.tools.items() if k in module_tools}

    @property
    def safe_tools(self) -> Dict[str, Tool[AgentDepsT]]:
        """
        Get safe functions for the agent.

        Returns:
            dict: A dictionary of safe function names and their corresponding Tool objects
                  that have the `safe_call` attribute set to True.
        """
        return {
            key: self.tools[key]
            for key in filter(
                lambda key: hasattr(self.tools[key].function, "safe_call"),
                self.tools.keys(),
            )
        }

    def tools_http_api(
        self,
        strict: bool = True,
        tools: list[Callable] | None = None,
        route_method: Literal["GET", "POST", "PUT", "DELETE"] = "GET",
    ) -> None:
        """
        Serve the tools as HTTP API endpoints using Server.

        This method creates a Server instance and adds routes for each tool registered with the agent.

        Args:
            tools (list[Callable]): A list of tool functions to expose as HTTP endpoints.
                                   If not provided, all tools registered with the agent will be used.
            route_method (str): The HTTP method to use for the routes. Default is "GET".

        Note:
            The tool functions will be exposed as endpoints with the function name as the path.
        """

        def add_tool_route(
            name: str, func: Callable, method: str = route_method
        ) -> None:
            annotations = get_type_hints(func)
            parameters = inspect.signature(func).parameters
            if any(
                param.kind
                in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
                for param in parameters.values()
            ):
                msg = (
                    f"Tool function '{name}' cannot have variable arguments (*args or **kwargs). "
                    "Please specify all parameters explicitly or pass strict=False with tools_http_api()"
                )
                if strict:
                    raise InvalidTool(msg)
                else:
                    vc.log(
                        f"{msg}, skipped to register as route",
                        bold=True,
                        color="red",
                        level_color="red",
                    )
                    return

            async def route_func(**kwargs):
                if hasattr(func, "iscoro") or asyncio.iscoroutinefunction(func):
                    return await func(**kwargs)
                return func(**kwargs)

            route_func.__name__ = name
            route_func.__signature__ = inspect.signature(func)
            route_func.__annotations__ = annotations
            route_func.__doc__ = func.__doc__

            self._router.add_api_route(
                path=f"/{name}",
                endpoint=route_func,
                methods=[method],
                name=name,
                summary=func.__doc__.strip().split("\n")[0] if func.__doc__ else None,
                description=func.__doc__,
            )

        if tools and isinstance(tools, (list, set, tuple)):
            for tool_func in tools:
                if not callable(tool_func):
                    vc.log(
                        f"Expected Callable got {tool_func}. "
                        f"[italic]{type(tool_func).__name__!r}[/] object is not callable",
                        bold=True,
                        color="red",
                    )
                    continue
                add_tool_route(name=tool_func.__name__, func=tool_func)
            return

        elif tools and not isinstance(tools, (list, set, tuple)):
            raise InvalidTools(
                f"Tools should be a iterable that contains callables, not {type(tools).__name__!r}."
            )

        for name, tool in self.tools.items():
            add_tool_route(name=name, func=tool.function)

        # Mark that tools_http_api has been called
        self._api.tools_http_api = _EnableFeature
        self._api.include_router(self._router)

    def on_error(self, func: Callable[[ErrorDict], Any]):
        """
        Add a error handler for the agent.
        This method allows you to set a function that will be called when an error occurs
        during the execution of the agent's tools.
        Args:
            func (Callable): The function to call that takes error data when an error occurs.
        """
        if (param_count := len(inspect.signature(func).parameters.keys())) != 1:
            raise (
                f"Error handler function {func.__name__!r} must take exactly one parameter, "
                f"but got {param_count} parameters."
            )

        self._handlers["errors"][func.__name__] = func

        vc.log(f"{func.__name__!r} error handler registered")

    def set_fix_agent(self, fix_agent: "VenusCode") -> None:
        """
        Set the fix agent for the Venus agent.

        This method allows you to set a fix agent that can be used to automatically fix errors
        in the tool functions.

        Args:
            fix_agent (VenusCode): The Venus agent to use for fixing errors.
        """
        self._fix_agent = fix_agent

    def fix(
        self,
        func: Callable[ToolParams, T],
    ) -> None:
        """
        Fix a function using the fix agent and store the results.

        Args:
            func (Callable): The function to fix.
            autofix (bool): Whether to automatically apply fixes.
            fix_always (bool): Whether to always apply the fix, even if it has been fixed before.
        Returns:
            ToolFuncContext[None, ToolParams]: The fixed function context.
        """
        func = decorators.autofix(func)
        filepath = inspect.getfile(func)
        source = inspect.getsource(func)

        vc.log(f"Autofix enabled for {func.__name__!r}")

        Fix = tinydb.Query()
        body = extract_function_body(func).strip()
        records = self.cachedb.search(
            (Fix.filepath == filepath) & (Fix.function == func.__name__)
        )
        records.sort(key=lambda x: x["fixdate"]["unix"], reverse=True)
        if records:
            record = records[0]
            if body in str(record):
                pretty_time = time_diff_prettify(
                    int(datetime.now().timestamp()) - record["fixdate"]["unix"]
                )
                (
                    vc.log(
                        f"Fix process for {func.__name__} skipped. Function already fixed once {pretty_time} ago"
                    )
                    if self.warnings
                    else None
                )
                return

        vc.log(f"Fix process for {func.__name__} started")

        ask = self.fix_agent.run_sync(
            f"Check function body, does this code REALLY `{extract_function_body(func)}` has errors? Assume imports are correct and there are no name errors",
            output_type=DoesNeedFix,
        )
        if ask.output.needs_fix:
            vc.log(f"Fixing {func.__name__!r} function using fix agent")
            for i, error in enumerate(ask.output.errors):
                vc.log(f"[{i}] {error}\n", color="red", bold=True)
        else:
            vc.log(
                f"No issues found in {func.__name__!r} function, skipping fix process"
            )
            return

        fix_result = self.fix_agent.run_sync(
            settings.custom_fix_prompt.format(source=source, filepath=filepath),
            output_type=FixFuncResult,
        )

        fix_time = datetime.now()
        fix_time_unix = int(fix_time.timestamp())

        fix_data = {
            "filepath": filepath,
            "source": source,
            "function": func.__name__,
            "result": fix_result.output.model_dump(),
            "fixdate": {
                "iso": fix_time.isoformat(),
                "unix": fix_time_unix,
            },
        }

        self.fixdb.insert(fix_data)
        self.cachedb.insert(fix_data)

    @overload
    def safe_plain(self, func: Callable[ToolParams, T]) -> ToolFuncPlain[ToolParams]:
        """
        Decorator to register a tool function with the agent and mark it as safe.

        Usage:
        ```python
        @agent.safe_plain
        def example(x: str, y: int) -> str:
            return f"Processed {x} and {y}"
        ```

        Args:
            func (Callable[ToolParams, T]): The function to register as a tool.

        Returns:
            ToolFuncPlain: The registered tool with the function wrapped in a safe call.
        """
        pass

    @overload
    def safe_plain(
        self,
        *,
        name: str | None = None,
        retries: int | None = None,
        strict: bool | None = None,
        autofix: bool = False,
        reload_function: bool = True,
        **options,
    ) -> Callable[[Callable[ToolParams, T]], ToolFuncPlain[ToolParams]]:
        """
        Decorator to register a tool function with the agent and mark it as safe.

        Usage:
        ```python
        @agent.safe_plain(name="tool_name", retries=3)
        async def example(x: str, y: int) -> str:
            return f"Processed {x} and {y}"
        ```

        Args:
            name (str): The name of the tool.
            retries (int): The number of retries for the tool function.
            strict (bool): Whether to enforce strict parameter checking.
            autofix (bool): Whether to automatically fix the function errors.
            **options: Additional options for the tool.

        Returns:
            Callable[[Callable[ToolParams, T]], ToolFuncPlain[ToolParams]]: Decorator function that returns ToolFuncPlain[ToolParams].
        """
        pass

    def safe_plain(
        self,
        func: Callable[ToolParams, T] | None = None,
        /,
        *,
        name: str | None = None,
        retries: int | None = None,
        strict: bool | None = None,
        autofix: bool = False,
        reload_function: bool = True,
        **options,
    ) -> Union[
        ToolFuncPlain[ToolParams],
        Callable[[Callable[ToolParams, T]], ToolFuncPlain[ToolParams]],
    ]:
        """
        Decorator to register a tool function with the agent and mark it as safe.

        This decorator registers the function as a safe tool that doesn't take RunContext
        as a parameter, unlike the regular `safe` decorator.

        Args:
            func (Callable[ToolParams, T]): The function to register as a tool.
            name (str): The name of the tool.
            retries (int): The number of retries for the tool function.
            strict (bool): Whether to enforce strict parameter checking.
            autofix (bool): Whether to automatically fix the function errors.
            reload_function (bool): Whether to reload the function after autofix.
            **options: Additional options for the tool.

        Returns:
            Union[ToolFuncPlain, Callable]: The registered tool or decorator function.

        Raises:
            InvalidContextParam: If the function is a context tool (should use `safe` instead).
        """

        def decorator(func: Callable[ToolParams, T]) -> ToolFuncPlain[ToolParams]:
            if autofix:
                func = decorators.autofix(func=func, reload_function=reload_function)
                self.fix(func)
            if is_context_tool(func):
                raise InvalidContextParam(
                    f"Function {func.__name__!r} is a context tool. Use `safe` decorator instead."
                )
            func.handlers = self._handlers
            func.fix_agent = self.fix_agent

            self.add_tool(
                function=safe_call(func),
                name=name,
                strict=strict,
                takes_ctx=False,
                max_retries=retries,
                **options,
            )
            return func

        if func is not None:
            if hasattr(func, "autofix") and func.autofix:
                func = decorators.autofix(func=func, reload_function=reload_function)
                self.fix(func)
            func.handlers = self._handlers
            func.fix_agent = self.fix_agent
            return decorator(func)
        return decorator

    @overload
    def safe(
        self, func: Callable[ToolParams, T] | None = None
    ) -> ToolFuncContext[None, ToolParams]:
        """
        Decorator to register a tool function with the agent and mark it as safe.

        Usage:

        ```python
        @agent.safe
        async def example(ctx: RunContext, x: str, y: int) -> str:
            return f"Processed {x} and {y}"
        ```

        Args:
            func (Callable[ToolParams, T]): The function to register as a tool.

        Returns:
            ToolFuncContext[None, ToolParams]: The registered tool with the function wrapped in a safe call.
        """
        pass

    @overload
    def safe(
        self,
        *,
        name: str | None = None,
        deps: Deps = Deps(),
        retries: int | None = None,
        strict: bool | None = None,
        autofix: bool = False,
        reload_function: bool = True,
        **options,
    ) -> Callable[[Callable[ToolParams, T]], ToolFuncContext[None, ToolParams]]:
        """
        Decorator to register a tool function with the agent and mark it as safe.

        Usage:
        ```python
        @agent.safe(name="tool_name", retries=3)
        async def example(ctx: RunContext, x: str, y: int) -> str:
            return f"Processed {x} and {y}"
        ```

        Args:
            name (str): The name of the tool.
            retries (int): The number of retries for the tool function.
            strict (bool): Whether to enforce strict parameter checking.
            autofix (bool): Whether to automatically fix the function errors.
            **options: Additional options for the tool.

        Returns:
            Callable[[Callable[ToolParams, T]], ToolFuncContext[None, ToolParams]]: Decorator function that returns ToolFuncContext[None, ToolParams].
        """
        pass

    def safe(
        self,
        func: Callable[ToolParams, T] | None = None,
        /,
        *,
        name: str | None = None,
        deps: Deps = Deps(),
        retries: int | None = None,
        strict: bool | None = None,
        autofix: bool = False,
        reload_function: bool = True,
        **options,
    ) -> Union[
        ToolFuncContext[None, ToolParams],
        Callable[[Callable[ToolParams, T]], ToolFuncContext[None, ToolParams]],
    ]:
        """
        Decorator to register a tool function with the agent and mark it as safe.

        This decorator registers the function as a safe tool that takes RunContext
        as its first parameter.

        Args:
            func (Callable[ToolParams, T]): The function to register as a tool.
            name (str): The name of the tool.
            retries (int): The number of retries for the tool function.
            strict (bool): Whether to enforce strict parameter checking.
            autofix (bool): Whether to automatically fix the function errors.
            **options: Additional options for the tool.

        Returns:
            Union[ToolFuncContext[None, ToolParams], Callable]: The registered tool or decorator function.

        Raises:
            InvalidContextParam: If the function doesn't have RunContext as first parameter.
        """

        def decorator(
            func: Callable[ToolParams, T],
        ) -> ToolFuncContext[None, ToolParams]:
            if autofix:
                func = decorators.autofix(func=func, reload_function=reload_function)
                self.fix(func)

            if not has_context_param(func):
                raise InvalidContextParam(
                    f"Function {func.__name__!r} must have parameter annotated with "
                    "RunContext as the first parameter."
                )
            func.handlers = self._handlers
            func.fix_agent = self.fix_agent
            if deps:
                func.deps = deps
            self.add_tool(
                function=safe_call(func),
                name=name,
                strict=strict,
                takes_ctx=True,
                max_retries=retries,
                **options,
            )
            return func

        if func is not None:
            if hasattr(func, "autofix") and func.autofix:
                func = decorators.autofix(func=func, reload_function=reload_function)
                self.fix(func)
            func.handlers = self._handlers
            func.fix_agent = self.fix_agent
            return decorator(func)
        return decorator

    @overload
    def autofix(self, func: Callable[ToolParams, T]) -> ToolFuncContext:
        """
        Decorator to automatically fix a function using the fix agent.

        Usage:
        ```python
        @agent.autofix
        async def example(ctx: RunContext, x: str, y: int) -> str:
            return f"Processed {x} and {y}"
        ```

        Args:
            func (Callable[ToolParams, T]): The function to register as a tool.

        Returns:
            ToolFuncContext: The registered tool with the function wrapped in an autofix call.
        """
        pass

    @overload
    def autofix(
        self,
        *,
        name: str | None = None,
        deps: Deps = Deps(),
        retries: int | None = None,
        strict: bool | None = None,
        reload_function: bool = True,
        **options,
    ) -> Callable[[Callable[ToolParams, T]], ToolFuncContext]:
        """
        Decorator to automatically fix a function using the fix agent.

        Usage:
        ```python
        @agent.autofix(name="tool_name", retries=3)
        async def example(ctx: RunContext, x: str, y: int) -> str:
            return f"Processed {x} and {y}"
        ```

        Args:
            name (str): The name of the tool.
            retries (int): The number of retries for the tool function.
            strict (bool): Whether to enforce strict parameter checking.
            reload_function (bool): Whether to reload the function after autofix.
            **options: Additional options for the tool.

        Returns:
            Callable[[Callable[ToolParams, T]], ToolFuncContext]: Decorator function that returns ToolFuncContext.
        """
        pass

    def autofix(
        self,
        func: Callable[ToolParams, T] | None = None,
        /,
        *,
        name: str | None = None,
        deps: Deps = Deps(),
        retries: int | None = None,
        strict: bool | None = None,
        reload_function: bool = True,
        **options,
    ) -> Union[
        ToolFuncContext,
        Callable[[Callable[ToolParams, T]], ToolFuncContext],
    ]:
        """
        Decorator to automatically fix a function using the fix agent.

        This decorator registers the function as a tool that will be automatically fixed
        using the fix agent if it encounters issues during execution. It supports both
        context-aware and plain functions.

        Args:
            func (Callable[ToolParams, T]): The function to register as a tool. Optional if used as a decorator.
            name (str, optional): The name of the tool. Defaults to the function's name.
            deps (Deps, optional): Dependencies to inject into the function. Defaults to an empty Deps object.
            retries (int, optional): The number of retries for the tool function. Defaults to None.
            strict (bool, optional): Whether to enforce strict parameter checking. Defaults to None.
            reload_function (bool, optional): Whether to reload the function after autofix. Defaults to True.
            **options: Additional options for the tool.

        Returns:
            Union[ToolFuncContext, Callable]: The registered tool or a decorator function if `func` is not provided.

        Raises:
            InvalidContextParam: If the function is context-aware but lacks a `RunContext` parameter.
        """
        reload_function = options.pop("reload", None) or reload_function

        def decorator(func: Callable[ToolParams, T]) -> ToolFuncContext:
            context_tool = True
            try:
                has_context_param(func)
            except (AssertionError, InvalidContextParam):
                context_tool = False
            safe_wrapper = self.safe if context_tool else self.safe_plain

            return safe_wrapper(
                func=func,
                name=name,
                deps=deps,
                strict=strict,
                retries=retries,
                autofix=True,
                reload_function=reload_function,
                **options,
            )

        return decorator(func) if func is not None else decorator

    @asynccontextmanager
    async def with_mcp_servers(self, mcp_servers: list[MCPServer] = []):
        self._user_toolsets += tuple(mcp_servers)
        async with self:
            yield self


class VenusCode(Venus, Generic[AgentDepsT, OutputDataT]):
    """
    VenusCode is a subclass of Venus specialized for writing and executing code.

    This class enhances the Venus agent with coding capabilities, optionally allowing
    code execution based on the execution_allowed parameter. It also supports sandbox
    environments for secure code execution.

    Attributes:
        coding_prompt (str | None): The custom coding prompt to use, if provided.
        execution_allowed (bool): Whether code execution is allowed.
        sandbox (bool): Whether to run code in a sandbox environment.
        sandbox_e2b (bool): Whether to use the e2b sandbox environment.
        warnings (bool): Whether to show warnings.
        tools (list[Callable]): The list of coding tools to use.

    Args:
        model (Model | KnownModelName | None): The model to use for the agent.
        fix_model (Model | KnownModelName | None): The model to use for fixing code.
        sandbox (bool): Whether to run code in a sandbox environment. Default is False.
        warnings (bool): Whether to show warnings. Default is True.
        permission (Permissions): The permission for the agent. Default is READ_WRITE.
        sandbox_e2b (bool): Whether to use the e2b sandbox environment. Default is False.
        execution_allowed (bool): Whether code execution is allowed. Default is False.
        coding_prompt (str | None): The custom coding prompt to use, if provided.
        **options: Additional options for the agent.

    Raises:
        InvalidTool: If any of the provided coding tools are not callable.
        ExecutionNotAllowed: If sandbox mode is enabled but code execution is not allowed.
    """

    def __init__(
        self,
        model: Model | KnownModelName | None = None,
        fix_model: Model | KnownModelName | None = None,
        sandbox: bool = False,
        warnings: bool = True,
        sandbox_e2b: bool = False,
        permitter: Callable[[Union[Permissions, int]], list[str]] = get_allowed_tools,
        permission: Permissions = Permissions.READ_WRITE,
        execution_allowed: bool = False,
        coding_prompt: str | None = None,
        **options,  # options for passing to Venus ctor
    ):
        load_dotenv(override=options.pop("override_env", False))

        execution_allowed = execution_allowed or (permission & Permissions.EXECUTE)

        name = options.pop("name", settings.agent_name)
        coding_tools = options.pop("tools", []) or tools
        if not all(map(callable, coding_tools)):
            raise InvalidTool(
                "All coding tools must be callable but some of the provided tools are not callable."
            )

        self._permitter_func = permitter or get_allowed_tools

        if not callable(self._permitter_func):
            raise InvalidFunction(
                "The permitter function must be callable. "
                "Please provide a valid function that returns allowed tool names."
            )

        user_prompt = options.pop("system_prompt", settings.system_prompt)
        if isinstance(user_prompt, tuple):
            user_prompt = ". ".join(user_prompt)
        user_prompt = user_prompt.format(name=name)

        if not coding_prompt:
            coding_prompt = settings.coding_prompt

        if coding_prompt != CODING_PROMPT and warnings:
            vc.log(
                "Before using new coding prompt, see default prompt at `venus.prompts.CODING_PROMPT`",
                bold=True,
            )
            coding_prompt = CODING_PROMPT

        system_prompt = f"{user_prompt}. {coding_prompt}."
        allowed_tools = self._permitter_func(permission)

        coding_tools = [t for t in coding_tools if t.__name__ in allowed_tools]

        if not permission & Permissions.WRITE:
            system_prompt += "You are not allowed to write files. "

        elif not execution_allowed:
            system_prompt += "You are not allowed to execute code. "

        self._tools = coding_tools

        super().__init__(
            model or settings.model_name,
            fix_model=fix_model or settings.fix_model,
            tools=self._tools,
            system_prompt=system_prompt,
            name=name,
            **options,
        )

        self._execution_allowed = execution_allowed

        if (sandbox or sandbox_e2b) and not execution_allowed:
            raise ExecutionNotAllowed(
                "Sandbox mode is enabled but code execution is not allowed. "
                "Please set `execution_allowed=True` to use sandbox mode."
            )

        if sandbox_e2b and execution_allowed:
            self.tools.clear()
            self._integrate_tool("venus.helpers.e2b")

        if not execution_allowed:
            self._function_toolset.tools.pop("execute_code", None)
            self._function_toolset.tools.pop("execute_script", None)
