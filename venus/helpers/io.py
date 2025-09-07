import asyncio
from pathlib import Path
from typing import Literal, Union

import aiofiles
import aiofiles.os
from mcp_run_python.code_sandbox import RunError, RunSuccess, code_sandbox
from venus.types import Safe

from ..decorators import safe_call
from ..types import FunctionToolset

"""
Tools for file operations.
"""


@safe_call
async def read_file_content(file_path: str) -> Safe[str]:
    """
    Reads the content of a file.

    Args:
        file_path (str): The path to the file.

    Returns:
        str: The content of the file.
    """
    async with aiofiles.open(file_path, "r") as file:
        return await file.read()


@safe_call
async def write_file_content(file_path: str, content: str) -> Safe[None]:
    """
    Writes content to a file.

    Args:
        file_path (str): The path to the file.
        content (str): The content to write to the file.
    """
    async with aiofiles.open(file_path, "w") as file:
        if not content:
            content = "silence is golden"
        await file.write(content)


@safe_call
async def append_file_content(file_path: str, content: str) -> Safe[None]:
    """
    Appends content to a file.

    Args:
        file_path (str): The path to the file.
        content (str): The content to append to the file.
    """
    async with aiofiles.open(file_path, "a") as file:
        await file.write(content)


@safe_call
async def delete_file(file_path: str) -> Safe[None]:
    """
    Deletes a file.

    Args:
        file_path (str): The path to the file.
    """
    await aiofiles.os.remove(file_path)


@safe_call
async def file_exists(file_path: str) -> Safe[bool]:
    """
    Checks if a file exists.

    Args:
        file_path (str): The path to the file.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    return await aiofiles.os.path.exists(file_path)


@safe_call
async def get_file_stats(file_path: str) -> Safe[dict]:
    """
    Gets the statistics of a file.

    Args:
        file_path (str): The path to the file.

    Returns:
        dict: A dictionary containing file statistics.
    """
    stats = await aiofiles.os.stat(file_path)
    return {
        "size": stats.st_size,
        "modified_time": stats.st_mtime,
        "access_time": stats.st_atime,
        "creation_time": stats.st_ctime,
        "other": {
            k.lstrip("st_"): getattr(stats, k)
            for k in dir(stats)
            if k.startswith("st_")
            and k not in ["st_size", "st_mtime", "st_atime", "st_ctime"]
        },
    }


@safe_call
async def execute_code(
    code: str, dependencies: list[str] | None = None, **options
) -> Safe[Union[RunSuccess, RunError]]:
    """
    Executes a script and returns the output.

    Args:
        code (str): The code to execute.
        dependencies (list[str] | None): List of dependencies to install.
        **options: Additional options to pass to the code by user.
    Returns:
        Union[RunSuccess, RunError]: The output of the code execution.
    """
    async with code_sandbox(dependencies=dependencies, **options) as interpreter:
        return await interpreter.eval(code)


@safe_call
async def execute_script(script: str) -> Safe[str]:
    """
    Executes a script and returns the output.

    Args:
        script (str): The script to execute.

    Returns:
        str: The output of the script.
    """
    process = await asyncio.create_subprocess_shell(
        script, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode() if stdout else stderr.decode()


@safe_call
async def make_dir(dir_path: str) -> Safe[None]:
    """
    Creates a directory.

    Args:
        dir_path (str): The path to the directory.
    """
    await aiofiles.os.makedirs(dir_path, exist_ok=True)


@safe_call
async def list_files(dir_path: str) -> Safe[list[tuple[str, bool]]]:
    """
    Lists all files in a directory.

    Args:
        dir_path (str): The path to the directory.

    Returns:
        list[tuple[str, bool]]: A list of tuples containing file names and is_directory flags.
    """
    return [
        (str(file), file.is_dir())
        for file in Path(dir_path).iterdir()
        if file.is_file()
    ]


@safe_call
async def rm_dir(dir_path: str) -> Safe[None]:
    """
    Removes a directory.

    Args:
        dir_path (str): The path to the directory.
    """
    rm_path = Path(dir_path)
    try:
        await aiofiles.os.rmdir(rm_path)
    except OSError as e:
        if e.errno == 66:
            for item in rm_path.iterdir():
                if item.is_dir():
                    await rm_dir(item)
                else:
                    await delete_file(item)
    finally:
        return await aiofiles.os.rmdir(dir_path)


@safe_call
def time_diff_prettify(diff: int) -> Safe[str]:
    """
    Converts a time difference in seconds to a human-readable format.

    Args:
        diff (int): The time difference in seconds.

    Returns:
        str: A human-readable string representing the time difference.
    """

    intervals = [
        (31556952, "year"),  # 365.24 * 24 * 3600
        (2629746, "month"),  # 365.24 * 24 * 3600 / 12
        (604800, "week"),  # 7 * 24 * 3600
        (86400, "day"),  # 24 * 3600
        (3600, "hour"),  # 60 * 60
        (60, "minute"),  # 60
        (1, "second"),
    ]

    for sec, name in intervals:
        if diff >= sec:
            count = diff // sec
            return f"{count} {name}{'s' if count != 1 else ''}"
    return "0 minute"


tools = [
    append_file_content,
    time_diff_prettify,
    write_file_content,
    read_file_content,
    get_file_stats,
    execute_script,
    execute_code,
    delete_file,
    file_exists,
    list_files,
    make_dir,
    rm_dir,
]

io_toolset = FunctionToolset(tools=tools, id="venus_io")
