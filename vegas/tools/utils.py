"""
Utility helper tools for text and data manipulation.
Exposes JSON formatting and word/character count with reading time estimation.
"""

import json

def format_json(data: str) -> str:
    """
    Parses and pretty-prints a raw JSON string.

    Args:
        data: The raw JSON string to be formatted.
    """
    try:
        parsed = json.loads(data)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError as e:
        return f"VEGAS: Invalid JSON input. Error detail: {str(e)}"
    except Exception as e:
        return f"VEGAS: Failed to format JSON: {str(e)}"

def word_count(text: str) -> str:
    """
    Calculates the word count, character count, and estimated reading time of the text.

    Args:
        text: The text content to analyze.
    """
    try:
        if not text.strip():
            return "VEGAS: Text is empty."
            
        words = len(text.split())
        chars = len(text)
        
        # Estimate reading time (average speed of 200 words per minute)
        wpm = 200
        total_seconds = int((words / wpm) * 60)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        if minutes > 0:
            reading_time = f"{minutes} min {seconds} sec"
        else:
            reading_time = f"{seconds} sec"
            
        return (
            f"Word Count: {words}\n"
            f"Character Count: {chars}\n"
            f"Estimated Reading Time: {reading_time}"
        )
    except Exception as e:
        return f"VEGAS: Failed to perform word count analysis: {str(e)}"

def register(mcp) -> None:
    """
    Registers the utility tools with the provided FastMCP server instance.
    """
    mcp.tool()(format_json)
    mcp.tool()(word_count)
