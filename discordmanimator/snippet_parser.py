"""Parser for extracting and validating Manim animation snippets."""

from __future__ import annotations

import ast
import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)


class SnippetInfo(NamedTuple):
    """Information about a parsed snippet.

    Attributes:
        raw_code: The original snippet code as extracted
        imports: List of import statement lines
        animation_function: The animation function code (class or function)
        function_name: Name of the detected animation function
        needs_wrapping: Whether the function needs to be wrapped in a Scene class
    """

    raw_code: str
    imports: list[str]
    animation_function: str
    function_name: str
    needs_wrapping: bool


def is_animation_function(node: ast.FunctionDef) -> bool:
    """Check if a function definition looks like an animation function.

    An animation function is a function with exactly one argument
    whose name is either 'self' or 'scene'.

    Args:
        node: AST FunctionDef node to check

    Returns:
        True if this looks like an animation function
    """
    args = node.args

    # Check for exactly one argument (excluding defaults, *args, **kwargs)
    if len(args.args) != 1:
        return False

    # Check if the argument is named 'self' or 'scene'
    arg_name = args.args[0].arg
    return arg_name in ("self", "scene")


def extract_non_animation_code(code: str, animation_func_name: str) -> list[str]:
    """Extract all code except the animation function.

    This includes imports, helper functions, assignments, etc.

    Args:
        code: Complete code snippet
        animation_func_name: Name of the animation function to exclude

    Returns:
        List of code lines that are not the animation function
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    non_animation_lines = []

    for node in ast.iter_child_nodes(tree):
        # Skip the animation function itself
        if isinstance(node, ast.FunctionDef) and node.name == animation_func_name:
            continue

        # Extract all other top-level code
        segment = ast.get_source_segment(code, node)
        if segment:
            non_animation_lines.append(segment)

    return non_animation_lines


def rename_function_to_construct(func_code: str, original_name: str) -> str:
    """Rename a function to 'construct'.

    The parameter name is left unchanged (self, scene, or whatever the user chose).

    Args:
        func_code: The function code as a string
        original_name: Original function name to replace

    Returns:
        Function code with name changed to 'construct'
    """
    try:
        tree = ast.parse(func_code)
    except SyntaxError:
        return func_code

    # Find the function definition and rename it
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == original_name:
            # Just change the function name
            node.name = "construct"
            break

    # Convert back to source code
    import ast as ast_module

    return ast_module.unparse(tree)


def parse_snippet(code: str) -> SnippetInfo | None:
    """Parse a code snippet and extract animation function information.

    Strategy:
    1. First check for a class with a 'construct' method
       - If found: use entire snippet as-is (no wrapping needed)
    2. Otherwise, look for an animation function (single arg: self/scene)
       - If found: extract just that function for wrapping, keep rest as-is

    Args:
        code: Python code snippet to parse

    Returns:
        SnippetInfo if a valid animation is found, None otherwise
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        logger.debug(f"Failed to parse snippet: {e}")
        return None

    # First pass: Check for class with construct method
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            # Check if any method in the class is named 'construct'
            for class_node in node.body:
                if (
                    isinstance(class_node, ast.FunctionDef)
                    and class_node.name == "construct"
                ):
                    # Found a class with construct - use entire snippet as-is
                    return SnippetInfo(
                        raw_code=code.strip(),
                        imports=[],
                        animation_function=code.strip(),
                        function_name=node.name,
                        needs_wrapping=False,
                    )

    # Second pass: Look for animation function that needs wrapping
    animation_func = None
    animation_func_name = None

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            if is_animation_function(node):
                # Extract just the animation function
                animation_func = ast.get_source_segment(code, node)
                animation_func_name = node.name
                break

    if animation_func is None:
        return None

    # Found animation function - return it separately for wrapping
    return SnippetInfo(
        raw_code=code.strip(),
        imports=[],
        animation_function=animation_func,  # Just the function
        function_name=animation_func_name,
        needs_wrapping=True,
    )


def extract_snippet_from_message(message: str) -> list[str]:
    """Extract code snippets from a Discord message.

    Looks for code blocks marked with ```python, ```py, or ``` that contain
    valid animation functions.

    Args:
        message: Discord message content

    Returns:
        List of code snippets that contain valid animation functions
    """
    import re

    # Match code blocks with optional python/py language tag
    pattern = re.compile(r"```(?:python|py)?\n?(.*?)```", re.DOTALL)
    code_blocks = pattern.findall(message)

    valid_snippets = []
    for code in code_blocks:
        snippet_info = parse_snippet(code)
        if snippet_info is not None:
            valid_snippets.append(code.strip())
            logger.debug(
                f"Found valid animation snippet: function={snippet_info.function_name}, "
                f"needs_wrapping={snippet_info.needs_wrapping}, "
                f"imports={len(snippet_info.imports)}"
            )

    return valid_snippets
