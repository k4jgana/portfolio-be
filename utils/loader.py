import os
import pystache

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "../prompts")


def load_prompt(name: str, context: dict = None) -> str:
    """
    Load a Mustache template from the prompts folder and render it with context.
    Args:
        name: Prompt file name (without extension)
        context: Dictionary of values for Mustache placeholders
    Returns:
        Rendered prompt as string
    """
    context = context or {}
    path = os.path.join(PROMPTS_DIR, f"{name}.mustache")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        template = f.read()

    return pystache.render(template, context)
