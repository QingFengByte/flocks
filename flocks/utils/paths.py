"""
Path utility helpers shared across Flocks modules.
"""

from pathlib import Path


def find_project_root() -> Path:
    """Walk up from cwd to locate the Flocks project root.

    Mimics how git locates ``.git/`` — searches the current directory and each
    ancestor in turn until it finds a directory that contains ``.flocks/``, or
    until the filesystem root is reached.

    Falls back to ``Path.cwd()`` when nothing is found (e.g. first-run before
    ``.flocks/`` has been created).

    Returns:
        The nearest ancestor directory (inclusive of cwd) that contains a
        ``.flocks/`` sub-directory, or ``Path.cwd()`` as a fallback.
    """
    current = Path.cwd().resolve()
    for directory in [current, *current.parents]:
        if (directory / ".flocks").is_dir():
            return directory
    return current


__all__ = ["find_project_root"]
