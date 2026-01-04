"""Tests for snippet parser module."""

from __future__ import annotations


from discordmanimator.snippet_parser import (
    extract_non_animation_code,
    extract_snippet_from_message,
    is_animation_function,
    parse_snippet,
    rename_function_to_construct,
)


class TestIsAnimationFunction:
    """Tests for is_animation_function helper."""

    def test_single_self_argument(self):
        """Test function with single 'self' argument."""
        import ast

        code = "def construct(self): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert is_animation_function(func_node) is True

    def test_single_scene_argument(self):
        """Test function with single 'scene' argument."""
        import ast

        code = "def animate(scene): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert is_animation_function(func_node) is True

    def test_no_arguments(self):
        """Test function with no arguments."""
        import ast

        code = "def my_func(): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert is_animation_function(func_node) is False

    def test_multiple_arguments(self):
        """Test function with multiple arguments."""
        import ast

        code = "def my_func(a, b): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert is_animation_function(func_node) is False

    def test_wrong_argument_name(self):
        """Test function with single argument but wrong name."""
        import ast

        code = "def my_func(other): pass"
        tree = ast.parse(code)
        func_node = tree.body[0]
        assert is_animation_function(func_node) is False


class TestParseSnippet:
    """Tests for parse_snippet function."""

    def test_simple_construct(self):
        """Test parsing a simple construct function."""
        code = """def construct(self):
    self.play(Create(Square()))"""

        result = parse_snippet(code)
        assert result is not None
        assert result.function_name == "construct"
        assert result.needs_wrapping is True
        assert result.imports == []
        assert "def construct(self):" in result.animation_function

    def test_construct_with_imports(self):
        """Test parsing construct with import statements."""
        code = """import numpy as np
from scipy import stats

def construct(self):
    self.play(Create(Square()))"""

        result = parse_snippet(code)
        assert result is not None
        assert result.function_name == "construct"
        assert result.needs_wrapping is True
        # animation_function should contain just the function
        assert (
            result.animation_function
            == "def construct(self):\n    self.play(Create(Square()))"
        )
        # raw_code should contain everything
        assert "import numpy as np" in result.raw_code
        assert "from scipy import stats" in result.raw_code

    def test_class_with_construct(self):
        """Test parsing a Scene class with construct method."""
        code = """class MyScene(Scene):
    def construct(self):
        self.play(Create(Circle()))"""

        result = parse_snippet(code)
        assert result is not None
        assert result.function_name == "MyScene"
        assert result.needs_wrapping is False
        assert "class MyScene(Scene):" in result.animation_function

    def test_scene_parameter(self):
        """Test parsing function with 'scene' parameter."""
        code = """def animate(scene):
    scene.play(Create(Square()))"""

        result = parse_snippet(code)
        assert result is not None
        assert result.function_name == "animate"
        assert result.needs_wrapping is True
        assert "def animate(scene):" in result.animation_function

    def test_invalid_syntax(self):
        """Test parsing code with syntax errors."""
        code = "def invalid syntax here"

        result = parse_snippet(code)
        assert result is None

    def test_no_animation_function(self):
        """Test parsing code without animation function."""
        code = """def helper(x, y):
    return x + y

result = helper(1, 2)"""

        result = parse_snippet(code)
        assert result is None

    def test_multiple_imports(self):
        """Test parsing with multiple types of imports."""
        code = """import os
import sys
from pathlib import Path
from typing import List, Dict

def construct(self):
    pass"""

        result = parse_snippet(code)
        assert result is not None
        assert result.needs_wrapping is True
        # animation_function should contain just the function
        assert result.animation_function.strip() == "def construct(self):\n    pass"
        # All imports should be in raw_code
        assert "import os" in result.raw_code
        assert "import sys" in result.raw_code
        assert "from pathlib import Path" in result.raw_code
        assert "from typing import List, Dict" in result.raw_code

    def test_class_with_imports(self):
        """Test parsing class with imports."""
        code = """import numpy as np

class MyAnimation(Scene):
    def construct(self):
        data = np.array([1, 2, 3])
        self.play(Create(Square()))"""

        result = parse_snippet(code)
        assert result is not None
        assert result.function_name == "MyAnimation"
        assert result.needs_wrapping is False
        # Entire snippet should be in animation_function
        assert "import numpy as np" in result.animation_function
        assert "class MyAnimation" in result.animation_function

    def test_class_construct_any_params(self):
        """Test parsing class where construct can have any parameters."""
        code = """class MyScene(Scene):
    def construct(self, extra_param=None):
        self.play(Create(Circle()))"""

        result = parse_snippet(code)
        assert result is not None
        assert result.function_name == "MyScene"
        assert result.needs_wrapping is False
        # The key is that it has a method named 'construct'

    def test_class_without_construct(self):
        """Test that class without construct method is invalid."""
        code = """class MyClass:
    def some_method(self):
        pass"""

        result = parse_snippet(code)
        assert result is None

    def test_function_with_helper_functions(self):
        """Test that helper functions are preserved when wrapping."""
        code = """import numpy as np

def helper(x):
    return x * 2

def construct(self):
    value = helper(5)
    self.play(Create(Square()))"""

        result = parse_snippet(code)
        assert result is not None
        assert result.function_name == "construct"
        assert result.needs_wrapping is True
        # animation_function should contain just construct
        assert "def construct(self):" in result.animation_function
        assert "def helper(x):" not in result.animation_function
        # raw_code should contain everything
        assert "import numpy as np" in result.raw_code
        assert "def helper(x):" in result.raw_code
        assert "def construct(self):" in result.raw_code

    def test_function_with_assignments(self):
        """Test that top-level assignments are preserved when wrapping."""
        code = """COLORS = [RED, BLUE, GREEN]
DURATION = 0.5

def construct(self):
    for color in COLORS:
        self.play(Create(Square(color=color)))"""

        result = parse_snippet(code)
        assert result is not None
        assert result.function_name == "construct"
        assert result.needs_wrapping is True
        # animation_function should contain just construct
        assert "def construct(self):" in result.animation_function
        # The assignment itself shouldn't be in animation_function
        assert "COLORS = [RED" not in result.animation_function
        assert "DURATION = 0.5" not in result.animation_function
        # raw_code should contain everything
        assert "COLORS = [RED, BLUE, GREEN]" in result.raw_code
        assert "DURATION = 0.5" in result.raw_code


class TestRenameFunctionToConstruct:
    """Tests for rename_function_to_construct helper."""

    def test_rename_construct_stays_unchanged(self):
        """Test that construct(self) stays unchanged."""
        func = """def construct(self):
    self.play(Create(Square()))"""

        result = rename_function_to_construct(func, "construct")
        assert "def construct(self):" in result
        assert "self.play" in result

    def test_rename_animate_preserves_scene(self):
        """Test renaming animate to construct while preserving 'scene' param."""
        func = """def animate(scene):
    scene.play(Create(Circle()))"""

        result = rename_function_to_construct(func, "animate")
        assert "def construct(scene):" in result
        assert "scene.play" in result

    def test_rename_custom_name_with_self(self):
        """Test renaming custom function that uses self."""
        func = """def my_animation(self):
    self.play(FadeIn(Text('Hello')))"""

        result = rename_function_to_construct(func, "my_animation")
        assert "def construct(self):" in result
        assert "self.play" in result

    def test_rename_preserves_function_body(self):
        """Test that complex function bodies are preserved."""
        func = """def animate(scene):
    for i in range(3):
        square = Square()
        scene.play(Create(square))
        scene.wait(0.5)"""

        result = rename_function_to_construct(func, "animate")
        assert "def construct(scene):" in result
        assert "for i in range(3):" in result
        assert "scene.play(Create(square))" in result
        assert "scene.wait(0.5)" in result

    def test_rename_preserves_custom_parameter(self):
        """Test that self/scene parameter names are preserved."""
        func = """def animate(scene):
    scene.play(Create(Square()))
    scene.wait()"""

        result = rename_function_to_construct(func, "animate")
        assert "def construct(scene):" in result
        assert "scene.play" in result
        assert "scene.wait" in result


class TestExtractNonAnimationCode:
    """Tests for extract_non_animation_code helper."""

    def test_extracts_imports(self):
        """Test extracting imports while excluding animation function."""
        code = """import numpy as np
from scipy import stats

def construct(self):
    pass"""

        result = extract_non_animation_code(code, "construct")
        assert len(result) == 2
        assert "import numpy as np" in result
        assert "from scipy import stats" in result

    def test_extracts_helper_functions(self):
        """Test extracting helper functions."""
        code = """def helper(x):
    return x * 2

def construct(self):
    value = helper(5)"""

        result = extract_non_animation_code(code, "construct")
        assert len(result) == 1
        assert "def helper(x):" in result[0]

    def test_extracts_assignments(self):
        """Test extracting top-level assignments."""
        code = """COLORS = [RED, BLUE, GREEN]
DURATION = 0.5

def construct(self):
    pass"""

        result = extract_non_animation_code(code, "construct")
        assert len(result) == 2
        assert any("COLORS" in line for line in result)
        assert any("DURATION" in line for line in result)

    def test_extracts_everything_except_animation(self):
        """Test extracting complex snippet with various elements."""
        code = """import numpy as np

GRID_SIZE = 3

def get_position(i, j):
    return RIGHT * i + UP * j

def construct(self):
    for i in range(GRID_SIZE):
        pass"""

        result = extract_non_animation_code(code, "construct")
        # Should have import, assignment, and helper function
        assert len(result) == 3
        assert any("import numpy" in line for line in result)
        assert any("GRID_SIZE" in line for line in result)
        assert any("def get_position" in line for line in result)


class TestExtractSnippetFromMessage:
    """Tests for extract_snippet_from_message function."""

    def test_simple_python_block(self):
        """Test extracting from ```python block."""
        message = """
Here's my animation:
```python
def construct(self):
    self.play(Create(Square()))
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 1
        assert "def construct(self):" in result[0]

    def test_py_language_tag(self):
        """Test extracting from ```py block."""
        message = """
```py
def construct(self):
    self.play(Create(Circle()))
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 1
        assert "def construct(self):" in result[0]

    def test_no_language_tag(self):
        """Test extracting from ``` block without language tag."""
        message = """
```
def construct(self):
    self.play(Create(Triangle()))
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 1
        assert "def construct(self):" in result[0]

    def test_multiple_code_blocks(self):
        """Test extracting from multiple code blocks."""
        message = """
First animation:
```python
def construct(self):
    self.play(Create(Square()))
```

Second animation:
```python
def construct(self):
    self.play(Create(Circle()))
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 2

    def test_no_valid_snippets(self):
        """Test message without valid animation snippets."""
        message = """
Some code:
```python
def regular_function(x, y):
    return x + y
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 0

    def test_mixed_valid_invalid(self):
        """Test message with both valid and invalid snippets."""
        message = """
Invalid:
```python
def helper(a, b):
    return a + b
```

Valid:
```python
def construct(self):
    self.play(Create(Square()))
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 1
        assert "def construct(self):" in result[0]

    def test_snippet_with_imports(self):
        """Test extracting snippet that has imports."""
        message = """
```python
import numpy as np
from typing import List

def construct(self):
    data = np.array([1, 2, 3])
    self.play(Create(Square()))
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 1
        assert "import numpy as np" in result[0]
        assert "def construct(self):" in result[0]

    def test_class_snippet(self):
        """Test extracting class-based snippet."""
        message = """
```python
class MyScene(Scene):
    def construct(self):
        self.play(Create(Square()))
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 1
        assert "class MyScene(Scene):" in result[0]

    def test_scene_parameter_function(self):
        """Test extracting function with scene parameter."""
        message = """
```python
def my_animation(scene):
    scene.play(FadeIn(Text("Hello")))
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 1
        assert "def my_animation(scene):" in result[0]

    def test_no_code_blocks(self):
        """Test message without any code blocks."""
        message = "Just a regular message with no code blocks"

        result = extract_snippet_from_message(message)
        assert len(result) == 0

    def test_empty_code_block(self):
        """Test message with empty code block."""
        message = """
```python
```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 0

    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        message = """
```python

def construct(self):
    self.play(Create(Square()))

```
        """

        result = extract_snippet_from_message(message)
        assert len(result) == 1
        # Result should be stripped of leading/trailing whitespace
        assert result[0].strip().startswith("def construct(self):")
