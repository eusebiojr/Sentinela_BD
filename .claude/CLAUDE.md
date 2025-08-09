# CLAUDE.md

This file provides comprehensive guidance to Claude Code when working with Python code in this repository.

## Core Development Philosophy

### KISS (Keep It Simple, Stupid)

Simplicity should be a key goal in design. Choose straightforward solutions over complex ones whenever possible. Simple solutions are easier to understand, maintain, and debug.

### YAGNI (You Aren't Gonna Need It)

Avoid building functionality on speculation. Implement features onlye when they are needed, not when you anticipate they might be useful in the future.

### Design Principles

- **Dependency Inversion**: High-level modules should not depend on low-level modules. Both should depend on abstractions.
- **Open/Closed Principle**: Software entities should be open for extension but closed for modification.
- **Single Responsibility**: Each function, class, and module should have one clear purpose.
- **Fail Fast**: Check for potential errors early and raise exceptions immediately when issues occur.

## Code Structure & Modularity

### File and Function Limits

- **Never createa file longer than 500 lines of code**. If approaching this limit, refactor by splitting it in modules.
- **Functions should be under 50 lines** with a single, clear responsibility.
- **Classes should be under 100 lines** and represent a single concept or entity.
- **Organize code into clearly separated modules**, grouped by feature or responsibility
- **Line lenght should be max 100 characters** ruff rule in pyproject.toml
- **Use venv_linux** (the virtual environment) whenever executing Python commands, including for unit tests

### Project Architecture

Follow strict vertical slice architecture with tests living next to the code they test:

...

src/project/
    __init__.py
    main.py
    tests/
        test_main.py
    conftest.py

    # Core modules
    database/
        __init__.py
        connection.py
        models.py
        tests/
            test_connection.py
            test_models.py

    auth/
        __init__.py
        authentication.py
        authorization.py
        tests/
            test_authentication.py
            test_authorization.py

    # Feature slices
    features/
        user_management/
            __init__.py
            handlers.py
            validators.py
            tests/
                test_handlers.py
                test_validators.py
...

## Testing Strategy

### Testing Best practices

### Test Organization

- Unit tests: Test individual functions/methods in isolation
- Integration tests: Test component interactions
- End-to-end tests: Test complete user workflows
- Keep test files nexto to the code they test
- Use 'conftest.py' for shared fixtures
- Aim for 80%+ code coverage, but focus on critical paths

## Error Handling

### Exception Best Practices

- **Use specific exceptions** over generic ones (ValueError, TypeError vs Exception)
- **Create custom exceptions** for domain-specific errors in a dedicated exceptions.py file
- **Always provide meaningful error messages** that help debug the issue
- **Never silence exceptions** withe bare except clauses
- **Use context managers** for resource management (with statements)
- **Implement retry logic** with exponential backoff for transient failures
- **Document expected exceptions** in functions docstrings

# Good - Specific and informative
class UserNotFoundError(Exception):
    """Raised when a user cannot be found in the database."""
    pass

def get_user(user_id: int) -> User:
    """
    Retrieve a user by ID.
    
    Raises:
        UserNotFoundError: If user_id doesn't exist
        ValueError: If user_id is negative
    """
    if user_id < 0:
        raise ValueError(f"Invalid user_id: {user_id}. Must be non-negative.")
    
    user = db.find_user(user_id)
    if not user:
        raise UserNotFoundError(f"No user found with ID: {user_id}")
    return user

# Bad - Too generic
def get_user(user_id):
    try:
        return db.find_user(user_id)
    except:  # Never do this
        return None

### logging strategy
- **Use Python's logging module**, never print() for production code
- **Configure logging levels** appropriately (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Include contextual information** in log messages (user_id, request_id, timestamps)
- **Use structured logging** with JSON format for production environments
- **Never log sensitive information** (passwords, tokens, PII)
- **Implement log rotation** to prevent disk space issues
- **Use correlation IDs** for tracking requests across services

# Configure logging at module level
import logging
from logging.handlers import RotatingFileHandler
import json

# Setup structured logging
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', None)
        }
        return json.dumps(log_data)

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File handler with rotation
handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=10_000_000,  # 10MB
    backupCount=5
)
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Usage examples
logger.info("User login successful", extra={'correlation_id': request_id, 'user_id': user.id})
logger.error(f"Database connection failed: {e}", exc_info=True)
logger.warning(f"API rate limit approaching: {current_rate}/{max_rate}")

## Debugging Tools

### Debugging Commands
- **Use debugger instead of print statements** for complex issues
- **Leverage IPython/ipdb** for interactive debugging
- **Profile code performance** with cProfile for optimization
- **Memory profiling** with memory_profiler for leak detection
- **Use pytest with -vv flag** for verbose test output
- **Enable Python warnings** during development

# Interactive debugging with ipdb
python -m ipdb script.py

# Set breakpoint in code
import ipdb; ipdb.set_trace()  # For debugging only, remove before commit

# Profile code performance
python -m cProfile -s cumulative script.py > profile_output.txt

# Memory profiling
python -m memory_profiler script.py

# Run tests with coverage and verbose output
python -m pytest -vv --cov=src --cov-report=html

# Enable all Python warnings
python -W all script.py

# Time execution of specific functions
python -m timeit -s "from module import function" "function()"

# Trace execution line by line
python -m trace --trace script.py

# Check for type errors with mypy
mypy src/ --strict

# Lint code with ruff
ruff check src/ --fix

# Format code with black
black src/ --line-length=100

## Debug Configuration for VS Code

{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Current File with Debugger",
            "type": "python",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal",
            "justMyCode": false,
            "env": {
                "PYTHONPATH": "${workspaceFolder}/src",
                "DEBUG": "true"
            }
        },
        {
            "name": "Python: pytest",
            "type": "python",
            "request": "launch",
            "module": "pytest",
            "args": ["-vv", "--tb=short"],
            "console": "integratedTerminal"
        }
    ]
}

### Common Debugging Patterns

# Conditional breakpoints for specific scenarios
if user_id == problematic_id:
    import ipdb; ipdb.set_trace()

# Logging function entry/exit
from functools import wraps

def debug_trace(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f"Entering {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Exiting {func.__name__} with result={result}")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            raise
    return wrapper

# Usage
@debug_trace
def complex_function(x, y):
    return x * y

## Git Workflow

### Branch Strategy

- 'main' - Production-ready code
- 'develop' - Integration branch for features
- 'feature/*' - New features
- 'fix'/*' - Bug fixes
- 'docs/*' - Documentation updates
- 'refactor/*' - Code refactoring
- 'test/*' - test additions or fixes

### Commit Message Format

Never include claude code, or written by claude code in commit messages

'''
<type>(<scope>): <subject>

<body>

<footer>
''

Types: feat, fix, docs, style, refactor, test, chore


## Documentation Standards

### Code Documentation

- Every module should have a docstring explaining its purpose
- Public functions must have complet docstrings
- Complex logic should have inline comments wit '# Reason:' prefix
- Keep README.md updated with setup instructions and examples
- Maintain CHANGELOG.md for version history

## Debugging Tools
pedir ia para criar
### Debugging Commands
pedir ia para criar

## Important Notes

- **NEVER ASSUME OR GUESS** - When in doubt, ask for clarification
- **Always verify file paths and module names** before use
- **Keep CLAUDE.md updated** when adding new patterns or dependencies
- **Test your code** - No feature is complete without tests
- **DOcument your decisions** - Future developers (including yourself) will thank you

## Search Command Requirements

**CRITICAL**: Always use 'rg' (ripgrep) instead of traditional 'grep' and 'find' commands:

'''bash
# Don't use grep
grep -r "pattern" .

# Use rg instead
rg "pattern"

# Don't use find with name
find . -name "*.py"

# Use rg with file filtering
rg --files | rg "\.py$"
# or
rg --files -g "*.py"


**Enforcement Rules:**

'''
(
    r"^grep\b(?!.*\|)",
    "Use 'rg' (ripgrep) instead of 'grep' for better performance and features",
),
(
    r"^find\s+\S+\s+-name\b",
    "Use 'rg --files | rg pattern' or 'rg --files -g -pattern' instead of 'find -name' for better performance",
),
'''