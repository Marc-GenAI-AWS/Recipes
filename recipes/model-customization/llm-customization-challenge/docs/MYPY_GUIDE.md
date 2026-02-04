# Mypy Type Checking Guide

## Overview

This project uses [mypy](https://mypy.readthedocs.io/) for static type checking to ensure code quality and catch type-related bugs before runtime. The configuration enforces strict type checking across the entire codebase as required by the design document.

## Configuration

The mypy configuration is defined in `mypy.ini` at the project root. Key features include:

### Strict Type Checking

- **Full type annotations required**: All functions must have complete type annotations
- **No untyped calls**: Cannot call functions without type annotations
- **Strict optional checking**: Proper handling of `None` and `Optional` types
- **No implicit `Any`**: Explicit type annotations required, no implicit `Any` types

### Relaxed Rules for Tests

Test files have slightly relaxed rules to allow for:
- Untyped pytest fixtures and decorators
- Helper functions without full type annotations
- More flexibility in test code structure

### Third-Party Library Handling

Libraries without type stubs (like boto3, streamlit) are configured to ignore missing imports, allowing development to proceed while still checking our own code strictly.

## Running Mypy

### Check All Source Code

```bash
# Activate virtual environment first
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run mypy on source code
mypy src
```

### Check Specific Files

```bash
mypy src/module_name.py
```

### Check Both Source and Tests

```bash
mypy src tests
```

### Generate HTML Report

```bash
mypy --html-report mypy-report src tests
```

Then open `mypy-report/index.html` in your browser.

### Verbose Output

```bash
mypy --verbose src/module_name.py
```

## Writing Type-Safe Code

### Basic Function Annotations

```python
def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"
```

### Optional Parameters

```python
from typing import Optional

def process_data(data: str, prefix: Optional[str] = None) -> str:
    """Process data with an optional prefix."""
    if prefix is None:
        return data
    return f"{prefix}{data}"
```

### Lists and Collections

```python
from typing import List, Dict, Set, Tuple

def process_items(items: List[str]) -> Dict[str, int]:
    """Count character length of each item."""
    return {item: len(item) for item in items}

def get_coordinates() -> Tuple[float, float]:
    """Return x, y coordinates."""
    return (10.5, 20.3)
```

### Classes with Type Annotations

```python
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class User:
    """User data model."""
    name: str
    email: str
    age: int
    tags: List[str]
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the user."""
        self.tags.append(tag)
    
    def get_display_name(self) -> str:
        """Get formatted display name."""
        return f"{self.name} ({self.email})"
```

### Generic Types

```python
from typing import TypeVar, Generic, List

T = TypeVar('T')

class Stack(Generic[T]):
    """A generic stack implementation."""
    
    def __init__(self) -> None:
        self._items: List[T] = []
    
    def push(self, item: T) -> None:
        """Push an item onto the stack."""
        self._items.append(item)
    
    def pop(self) -> T:
        """Pop an item from the stack."""
        return self._items.pop()
```

### Async Functions

```python
from typing import List
import asyncio

async def fetch_data(url: str) -> str:
    """Fetch data from URL asynchronously."""
    # Implementation here
    return "data"

async def fetch_multiple(urls: List[str]) -> List[str]:
    """Fetch data from multiple URLs."""
    tasks = [fetch_data(url) for url in urls]
    return await asyncio.gather(*tasks)
```

## Common Type Checking Issues

### Issue: Missing Return Type

```python
# ❌ Bad - missing return type
def calculate(x, y):
    return x + y

# ✅ Good - explicit return type
def calculate(x: int, y: int) -> int:
    return x + y
```

### Issue: Untyped Parameters

```python
# ❌ Bad - untyped parameters
def process(data):
    return data.upper()

# ✅ Good - typed parameters
def process(data: str) -> str:
    return data.upper()
```

### Issue: Implicit Any

```python
# ❌ Bad - implicit Any from untyped function
def get_value():
    return 42

result = get_value()  # result has type Any

# ✅ Good - explicit return type
def get_value() -> int:
    return 42

result = get_value()  # result has type int
```

### Issue: Optional Not Handled

```python
from typing import Optional

# ❌ Bad - not checking for None
def get_length(text: Optional[str]) -> int:
    return len(text)  # Error: text might be None

# ✅ Good - checking for None
def get_length(text: Optional[str]) -> int:
    if text is None:
        return 0
    return len(text)
```

## Ignoring Type Errors

Sometimes you need to ignore type errors (e.g., when dealing with dynamic code or known limitations). Use `# type: ignore` sparingly:

```python
# Ignore specific error on one line
result = dynamic_function()  # type: ignore

# Ignore with explanation
result = legacy_code()  # type: ignore[attr-defined]  # Legacy code without types
```

**Note**: Overuse of `# type: ignore` defeats the purpose of type checking. Only use when absolutely necessary.

## Integration with Development Workflow

### Pre-commit Hook

Add mypy to your pre-commit checks:

```bash
# .git/hooks/pre-commit
#!/bin/bash
mypy src
if [ $? -ne 0 ]; then
    echo "Mypy type checking failed. Please fix type errors before committing."
    exit 1
fi
```

### CI/CD Integration

Add mypy to your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run mypy
  run: |
    pip install mypy
    mypy src tests
```

### IDE Integration

Most modern IDEs support mypy integration:

- **VS Code**: Install the "Pylance" extension (includes mypy support)
- **PyCharm**: Built-in type checking with mypy support
- **Vim/Neovim**: Use ALE or coc-pyright plugins

## Troubleshooting

### Mypy Cache Issues

If you encounter strange errors, try clearing the mypy cache:

```bash
rm -rf .mypy_cache
mypy src
```

### Import Errors for Third-Party Libraries

If mypy complains about missing imports for third-party libraries:

1. Check if type stubs are available: `pip install types-<library-name>`
2. If no stubs exist, add to `mypy.ini`:

```ini
[mypy-library_name.*]
ignore_missing_imports = True
```

### Performance Issues

For large codebases, mypy can be slow. Optimizations:

1. Use incremental mode (enabled by default in our config)
2. Run mypy only on changed files during development
3. Use `--no-incremental` flag if cache causes issues

## Best Practices

1. **Write types as you code**: Don't add types as an afterthought
2. **Use type aliases**: For complex types, create aliases for readability
3. **Leverage dataclasses**: Use `@dataclass` for data structures
4. **Document with types**: Types serve as documentation
5. **Run mypy regularly**: Integrate into your development workflow
6. **Fix errors promptly**: Don't let type errors accumulate

## Resources

- [Mypy Documentation](https://mypy.readthedocs.io/)
- [Python Type Hints (PEP 484)](https://www.python.org/dev/peps/pep-0484/)
- [Typing Module Documentation](https://docs.python.org/3/library/typing.html)
- [Type Hints Cheat Sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)

## Project-Specific Notes

### AWS SDK Types

The AWS SDK (boto3) doesn't have complete type stubs. When working with AWS services:

```python
from typing import Any, Dict
import boto3

def create_client(service_name: str) -> Any:
    """Create AWS service client.
    
    Note: boto3 clients don't have complete type information,
    so we use Any here. Consider using boto3-stubs for better types.
    """
    return boto3.client(service_name)
```

### Pydantic Integration

We use the pydantic mypy plugin for better dataclass support. This provides:

- Validation of field types
- Better error messages for pydantic models
- Integration with pydantic's runtime validation

### Test Files

Test files have relaxed type checking rules. However, it's still good practice to add types where reasonable:

```python
import pytest
from typing import List

@pytest.fixture
def sample_data() -> List[int]:
    """Provide sample data for tests."""
    return [1, 2, 3, 4, 5]

def test_something(sample_data: List[int]) -> None:
    """Test something with sample data."""
    assert len(sample_data) == 5
```

## Summary

Mypy is configured to enforce strict type checking across the codebase, ensuring:

1. ✅ Full type annotations with mypy validation
2. ✅ Strict type checking configuration
3. ✅ Appropriate exclusions for test files and third-party code
4. ✅ Integration with development workflow

By following this guide and maintaining proper type annotations, we ensure code quality, catch bugs early, and improve code maintainability.
