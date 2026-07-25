"""
Developer, coding, and file system tools for the Vegas Assistant.
Allows VEGAS to write code, manage files, and run commands autonomously.
"""

import os
import subprocess
import re
from vegas.safety import requires_confirmation

@requires_confirmation
def run_command(command: str, cwd: str = ".") -> str:
    """
    Executes a shell command on the host system and returns its output (stdout and stderr).
    Use this to run tests, build projects, or execute scripts.

    Args:
        command: The shell command to run.
        cwd: The working directory in which to execute the command (defaults to current directory).
    """
    try:
        # Resolve absolute path for cwd
        target_cwd = os.path.abspath(cwd)
        # Execute the command
        result = subprocess.run(
            command,
            shell=True,
            cwd=target_cwd,
            text=True,
            capture_output=True,
            timeout=60 # 60 seconds timeout
        )
        output = []
        if result.stdout:
            output.append(f"[STDOUT]\n{result.stdout}")
        if result.stderr:
            output.append(f"[STDERR]\n{result.stderr}")
        
        status = f"Command exited with code {result.returncode}."
        if not output:
            return f"{status}\n(No output)"
        full_text = f"{status}\n" + "\n".join(output)
        if len(full_text) > 10000:
            return full_text[:10000] + "\n\n[...truncated output to 10,000 characters]"
        return full_text
    except subprocess.TimeoutExpired:
        return "VEGAS: Command timed out after 60 seconds."
    except Exception as e:
        return f"VEGAS: Failed to run command: {str(e)}"

def list_directory(path: str = ".") -> str:
    """
    Lists files and directories at the specified path.

    Args:
        path: The path of the directory to list (defaults to current directory).
    """
    try:
        target_path = os.path.abspath(path)
        if not os.path.exists(target_path):
            return f"VEGAS: Path '{path}' does not exist."
        if not os.path.isdir(target_path):
            return f"VEGAS: Path '{path}' is a file, not a directory."
        
        items = os.listdir(target_path)
        result = []
        for item in sorted(items):
            item_path = os.path.join(target_path, item)
            is_dir = os.path.isdir(item_path)
            prefix = "[DIR] " if is_dir else "[FILE]"
            size = "" if is_dir else f" ({os.path.getsize(item_path)} bytes)"
            result.append(f"{prefix} {item}{size}")
            
        if not result:
            return f"Directory '{path}' is empty."
        return "\n".join(result)
    except Exception as e:
        return f"VEGAS: Failed to list directory: {str(e)}"

def view_file(path: str) -> str:
    """
    Reads and returns the contents of a file.

    Args:
        path: The path to the file.
    """
    try:
        target_path = os.path.abspath(path)
        if not os.path.exists(target_path):
            return f"VEGAS: File '{path}' does not exist."
        if os.path.isdir(target_path):
            return f"VEGAS: Path '{path}' is a directory, use list_directory instead."
            
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return content
    except Exception as e:
        return f"VEGAS: Failed to view file: {str(e)}"

@requires_confirmation
def write_file(path: str, content: str) -> str:
    """
    Creates or overwrites a file with the specified content.

    Args:
        path: The path to the file.
        content: The content to write to the file.
    """
    try:
        target_path = os.path.abspath(path)
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"VEGAS: Successfully wrote to file: {path}"
    except Exception as e:
        return f"VEGAS: Failed to write file: {str(e)}"

@requires_confirmation
def edit_file(path: str, search: str, replace: str) -> str:
    """
    Surgically replaces a specific block of text in a file.
    Only updates if the 'search' block is found exactly once in the file.

    Args:
        path: The path to the file.
        search: The exact block of text to search for.
        replace: The replacement block of text.
    """
    try:
        target_path = os.path.abspath(path)
        if not os.path.exists(target_path):
            return f"VEGAS: File '{path}' does not exist."
            
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        occurrences = content.count(search)
        if occurrences == 0:
            return "VEGAS: Search content not found. Make sure spelling and whitespace match exactly."
        if occurrences > 1:
            return f"VEGAS: Search content found {occurrences} times. Provide more unique surrounding context."
            
        new_content = content.replace(search, replace, 1)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"VEGAS: Successfully modified file: {path}"
    except Exception as e:
        return f"VEGAS: Failed to edit file: {str(e)}"

def search_directory(query: str, path: str = ".") -> str:
    """
    Searches for files containing a specific text query within a directory.

    Args:
        query: The text pattern to search for.
        path: The root path to search in (defaults to current directory).
    """
    try:
        target_path = os.path.abspath(path)
        results = []
        for root, dirs, files in os.walk(target_path):
            # Skip common search-noisy folders
            if any(folder in root for folder in [".git", "__pycache__", ".venv", "node_modules"]):
                continue
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if query in line:
                                rel_path = os.path.relpath(file_path, target_path)
                                results.append(f"{rel_path}:{line_num}: {line.strip()}")
                                if len(results) >= 50:
                                    break
                except Exception:
                    pass
                if len(results) >= 50:
                    break
            if len(results) >= 50:
                break
                
        if not results:
            return f"VEGAS: No matches found for '{query}'."
        return "\n".join(results)
    except Exception as e:
        return f"VEGAS: Search directory failed: {str(e)}"

def register(mcp) -> None:
    """
    Registers developer tools with the FastMCP server.
    """
    mcp.tool()(run_command)
    mcp.tool()(list_directory)
    mcp.tool()(view_file)
    mcp.tool()(write_file)
    mcp.tool()(edit_file)
    mcp.tool()(search_directory)
