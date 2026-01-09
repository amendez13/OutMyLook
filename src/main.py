"""Main entry point for OutMyLook."""

from typing import Optional


def greet(name: Optional[str] = None) -> str:
    """Return a greeting message.

    Args:
        name: Optional name to greet. Defaults to "World".

    Returns:
        A greeting string.
    """
    if name is None:
        name = "World"
    return f"Hello, {name}!"


def main() -> None:
    """Main entry point."""
    print(greet())


if __name__ == "__main__":
    main()
