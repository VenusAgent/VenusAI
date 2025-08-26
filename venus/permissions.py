"""
Permissions module for the Venus agent.
"""

from enum import IntFlag


class Permissions(IntFlag):
    """
    Permissions for file operations.
    """

    READ = 0b00001
    WRITE = 0b00010
    APPEND = 0b00100
    EXECUTE = 0b01000
    CHECK = 0b10000

    READ_ONLY = READ | CHECK
    WRITE_ONLY = WRITE | CHECK
    APPEND_ONLY = APPEND | CHECK

    READ_WRITE = READ | WRITE | CHECK
    READ_APPEND = READ | APPEND | CHECK
    WRITE_APPEND = READ | WRITE | APPEND | CHECK
    READ_EXECUTE = READ | EXECUTE | CHECK
    WRITE_EXECUTE = READ | WRITE | EXECUTE | CHECK
    APPEND_EXECUTE = READ | APPEND | EXECUTE | CHECK
    ALL = READ | WRITE | APPEND | EXECUTE | CHECK


def get_allowed_tools(permissions: int) -> list[str]:
    """
    Get the allowed tools based on the provided permissions.

    Args:
        permissions (int): The permissions bitmask.

    Returns:
        list[str]: A list of allowed tool names.
    """
    allowed_tools = {"time_diff_prettify"}

    if permissions & Permissions.READ:
        allowed_tools.update({"read_file_content"})

    if permissions & Permissions.WRITE:
        allowed_tools.update(
            {
                "append_file_content",
                "write_file_content",
                "make_dir",
                "delete_file",
                "rm_dir",
                "read_file_content",
                "get_file_stats",
                "list_files",
                "file_exists",
            }
        )

    if permissions & Permissions.APPEND:
        allowed_tools.update({"append_file_content"})

    if permissions & Permissions.EXECUTE:
        allowed_tools.update({"execute_code", "execute_script"})

    if permissions & Permissions.CHECK:
        allowed_tools.update({"file_exists", "get_file_stats", "list_files"})

    if permissions == Permissions.ALL:
        allowed_tools.update(
            {
                "append_file_content",
                "read_file_content",
                "write_file_content",
                "file_exists",
                "get_file_stats",
                "execute_script",
                "execute_code",
                "delete_file",
                "list_files",
                "make_dir",
                "rm_dir",
            }
        )

    return sorted(allowed_tools)
