"""
Prompt templates for the Vegas Assistant.
Exposes register_all_prompts(mcp) to register prompts with FastMCP.
"""

def summarize(text: str) -> str:
    """
    Instructs the model to generate a concise 3-bullet point summary of the text.

    Args:
        text: The source text to be summarized.
    """
    return (
        "Please analyze the following text and provide a concise, high-level summary. "
        "Your summary MUST be formatted exactly as three bullet points. Be clear and direct.\n\n"
        f"Text to summarize:\n{text}"
    )

def explain_code(code: str, language: str = "python") -> str:
    """
    Instructs the model to explain a code snippet clearly for a beginner.

    Args:
        code: The raw code snippet.
        language: The programming language of the snippet (default "python").
    """
    return (
        f"You are a friendly and expert programming instructor. Explain the following {language} code "
        "snippet clearly and simply so a beginner can understand it. Break down the key concepts, "
        "explain what each part does, and summarize the overall purpose of the code.\n\n"
        f"Code snippet:\n```{language}\n{code}\n```"
    )

def register_all_prompts(mcp) -> None:
    """
    Registers prompt templates with the provided FastMCP server instance.
    """
    mcp.prompt()(summarize)
    mcp.prompt()(explain_code)
