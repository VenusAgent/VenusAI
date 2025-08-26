"""
E2B Code Interpreter implementation for sandboxed code execution.
"""

import asyncio
from typing import Literal, TypeVar, Union

from ...decorators import safe_call
from ...types import FunctionToolset, Safe
from ._client import _request_timeout, sandbox

request_timeout = _request_timeout or 10

T = TypeVar("T")


def format(value: T) -> Union[T, str]:
    """
    Format the value for safe representation.

    Args:
        value (Any): The value to format.
    """
    val_type = type(value)
    if getattr(val_type, "__module__", None) == "builtins":
        return value
    else:
        return repr(value)


@safe_call
async def list_files(dir_path: str) -> Safe[T]:
    """
    List files in a directory in the sandboxed environment.

    Args:
        dir_path (str): The path to the directory to list files from.
    """
    return format(await asyncio.to_thread(sandbox.files.list, dir_path))


@safe_call
async def rename_file(cur_path: str, new_path: str) -> Safe[T]:  # mark
    """
    Append content to a file in the sandboxed environment.

    Args:
        file_path (str): The path to the file to append to.
        content (str): The content to append to the file.
        format (Literal['text', 'bytes']): The format to write the file in, either 'text' or 'bytes'.
    """
    return format(await asyncio.to_thread(sandbox.files.rename, cur_path, new_path))


@safe_call
async def file_exists(file_path: str) -> Safe[T]:
    """
    Check if a file exists in the sandboxed environment.

    Args:
        file_path (str): The path to the file to check.
    """
    return format(await asyncio.to_thread(sandbox.files.exists, file_path))


@safe_call
async def make_dir(dir_path: str) -> Safe[T]:
    """
    Create a directory in the sandboxed environment.

    Args:
        dir_path (str): The path to the directory to create.
    """
    return format(await asyncio.to_thread(sandbox.files.make_dir, dir_path))


@safe_call
async def rm_dir(dir_path: str) -> Safe[T]:
    """
    Remove a directory in the sandboxed environment.

    Args:
        dir_path (str): The path to the directory to remove.
    """
    return format(await asyncio.to_thread(sandbox.files.remove, dir_path))


@safe_call
async def read_file_content(
    file_path: str, format: Literal["text", "bytes"] = "text"
) -> Safe[T]:
    """
    Read a file from the sandboxed environment.

    Args:
        file_path (str): The path to the file to read.
        format (Literal['text', 'bytes']): The format to read the file in, either 'text' or 'bytes'.
    """
    return format(await asyncio.to_thread(sandbox.files.read, file_path, format=format))


@safe_call
async def write_file_content(file_path: str, content: str) -> Safe[T]:
    """
    Write content to a file in the sandboxed environment.

    Args:
        file_path (str): The path to the file to write.
        content (str): The content to write to the file.
        format (Literal['text', 'bytes']): The format to write the file in, either 'text' or 'bytes'.
    """
    return format(await asyncio.to_thread(sandbox.files.write, file_path, content))


@safe_call
async def execute_code(code: str, timeout: int = 10) -> Safe[T]:
    """
    Execute code in a sandboxed environment.

    Args:
        code (str): The code to execute.
        timeout (int): Maximum time in seconds to allow for execution.
    """
    return format(await asyncio.to_thread(sandbox.run_code, code, timeout=timeout))


tools = [
    write_file_content,
    read_file_content,
    execute_code,
    rename_file,
    file_exists,
    list_files,
    make_dir,
    rm_dir,
]

e2b_toolset = FunctionToolset(tools=tools, id="e2b")
