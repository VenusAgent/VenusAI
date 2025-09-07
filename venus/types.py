"""
This is a module that provides various types and classes for the Venus AI agent.
"""

import importlib
from types import EllipsisType, GenericAlias
from typing import (Any, Awaitable, Callable, Generic, Literal, ParamSpec,
                    TypeAlias, TypeVar, Union, cast, get_origin,
                    get_type_hints)

from pydantic import TypeAdapter
from pydantic_core.core_schema import AnySchema, any_schema

from attrobj import Object
from pydantic_ai import ModelRetry
from pydantic_ai._run_context import AgentDepsT, RunContext
from pydantic_ai.agent import Agent
from pydantic_ai.mcp import (MCPServerSSE, MCPServerStdio,
                             MCPServerStreamableHTTP)
from pydantic_ai.models import KnownModelName
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.providers.grok import GrokProvider
from pydantic_ai.providers.openai import OpenAIProvider, Provider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import FunctionToolset

ReturnType = TypeVar("ReturnType")
FuncParams = ParamSpec("FuncParams")
CallableType = TypeVar("CallableType", bound=Callable)
CacheManagerType = TypeVar("CacheManagerType")
CacheTypes = Literal[
    "python-lru", "async-lru", "fifo", "lfu", "lru", "rr", "tlru", "ttl"
]

# Type variables
T = TypeVar("T")  # for general types
MainType = TypeVar("MainType")
GetDepsT = TypeVar("GetDepsT")
ReturnType = TypeVar("ReturnType")
DepsT = TypeVar("DepsT", bound=Any)
EnableFeatureT = TypeVar("EnableFeatureT", bound=EllipsisType)


# Type aliases
_EnableFeature: TypeAlias = EnableFeatureT
"""Sentinel value to indicate that a feature is enabled."""

ErrorDict = dict  # pseudo alias
Safe = MainType | ErrorDict
Entity = Any  # pseudo alias

ToolsPrepareFunc: TypeAlias = Callable[
    [RunContext[AgentDepsT], list[ToolDefinition]],
    Awaitable[list[ToolDefinition] | None],
]

get_type = lambda func, param: cast(type, get_type_hints(func).get(param, None))
"""
Get the type of a parameter in a function.
Args:
    func (Callable[..., Any]): The function to get the type from.
    param (str): The parameter name.
Returns:
    type: The type of the parameter.
"""

get_base_type = lambda func, param: cast(
    type, get_origin(get_type(func, param)) or get_type(func, param)
)
"""
Get the base type of a parameter in a function.
Args:
    func (Callable[..., Any]): The function to get the type from.
    param (str): The parameter name.
Returns:
    type: The base type of the parameter.
"""


class Deps(Object, Generic[DepsT]):
    """
    A class that extends Object to provide a dictionary-like interface for dependencies.
    This class allows for dynamic access to dependencies as attributes.

    Usage:
    - deps[DepType]
    - deps[key]
    """

    @property
    def main(self) -> DepsT:
        """
        Raw dependency value will be stored in main field for backward compatibility.
        """
        return self.get("main")

    def __init__(self, data: dict = {}, **kwargs):
        """
        Initializes the Deps object with the given data and optional dependencies.

        Args:
            data (dict, optional): The initial data for the Deps object.
            **kwargs (T, optional): Optional dependencies that can be used to initialize the Deps object.
        """

        super().__init__(**(data or kwargs))

    def __bool__(self) -> bool:
        """Returns True if the Deps object is not empty."""
        return bool(list(self.keys()))

    def __str__(self):
        """Returns a string representation of the Deps object."""
        return repr(self)

    def __repr__(self) -> str:
        """Returns a string representation of the Deps object."""
        return f"Deps({super().__repr__()})"

    def get(self, key: str | type[GetDepsT], default: Any = None) -> GetDepsT:
        """
        Returns the value for the given key, or the default value if the key does not exist.

        Args:
            key (str): The key to look up.
            default (T, optional): The default value to return if the key does not exist.

        Returns:
            DepsT: The value for the given key or the default value.
        """
        if not isinstance(key, str) and (
            hasattr(key, "__class_getitem__") or isinstance(key, GenericAlias)
        ):
            try:
                adapter = TypeAdapter(key)
            except:
                return super().get(key, default)
            for v in self.values():
                try:
                    adapter.validate_python(v)
                    return v
                except:
                    continue
        key = key if isinstance(key, str) else get_origin(key) or key
        return super().get(key, default)

    @classmethod
    def new(cls, **kwargs) -> "Deps":
        """
        Creates a new instance of the Deps class with the given keyword arguments.

        Args:
            **kwargs: Keyword arguments to initialize the Deps object.

        Returns:
            Deps: A new instance of the Deps class.
        """
        return cls(kwargs)

    def __getattr__(self, name: str) -> Any | Object:
        """
        Customizes attribute access for dictionary-like objects.

        Args:
            name (str): The name of the attribute being accessed.

        Returns:
            Any: The value associated with the attribute name if it exists as a key,
             otherwise the result of default attribute lookup.
        """
        return super().__getattr__(name)

    def __get_pydantic_core_schema__(self, *args, **kwargs) -> AnySchema:
        """
        Returns the Pydantic core schema for the Deps object.

        This method is used to provide a schema for serialization and validation.

        Returns:
            AnySchema: The Pydantic core schema for the Deps object.
        """
        return any_schema()


def __getattr__(name: str) -> Entity:
    """
    Dynamic attribute access for the Deps object.

    Args:
        name (str): The name of the attribute to access.

    Returns:
        Any: The value of the attribute.
    """

    def _get_type(name: str) -> Union[Entity, type[Entity]]:
        """
        Attempts to import the type from the specified namespaces.

        Args:
            name (str): The name of the type to get.

        Returns:
            type[Entity]: The type if found, otherwise raises AttributeError.
        """
        last_ns = "pydantic_ai"
        fallbacks = [
            "pydantic_ai",
            "pydantic_ai.agent",
            "pydantic_ai.tools",
            "pydantic_ai.mcp",
            "pydantic_ai.models",
            "pydantic_ai.providers",
            "pydantic_ai.toolsets",
            "pydantic_ai.messages",
        ]

        for ns in fallbacks:
            last_ns = ns
            try:
                lib = importlib.import_module(ns)
                return getattr(lib, name)
            except:
                continue
        raise AttributeError(f"Can not import '{name}' from '{last_ns}' namespace.")

    return _get_type(name)
