#!/usr/bin/env python3
"""Bump version across all configuration files.

Usage:
    python scripts/bump_version.py 0.2.0
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

FILES_TO_UPDATE = [
    ("pyproject.toml", r'version = "[^"]+"', 'version = "{version}"'),
    ("package.json", r'"version": "[^"]+"', '"version": "{version}"'),
    ("dash_bucket_upload/package-info.json", r'"version": "[^"]+"', '"version": "{version}"'),
]


def bump_version(new_version: str) -> None:
    """Update version in all configuration files."""
    # Validate version format
    if not re.match(r'^\d+\.\d+\.\d+(-[\w.]+)?$', new_version):
        print(f"Error: Invalid version format '{new_version}'. Expected format: X.Y.Z or X.Y.Z-suffix")
        sys.exit(1)

    print(f"Bumping version to {new_version}")

    for filepath, pattern, replacement in FILES_TO_UPDATE:
        full_path = PROJECT_ROOT / filepath
        if not full_path.exists():
            print(f"  Warning: {filepath} not found, skipping")
            continue

        content = full_path.read_text()
        new_content = re.sub(pattern, replacement.format(version = new_version), content, count = 1)

        if content == new_content:
            print(f"  Warning: No version found in {filepath}")
        else:
            full_path.write_text(new_content)
            print(f"  Updated {filepath}")

    print("\nVersion bump complete!")
    print("\nNext steps:")
    print("  1. Review changes: git diff")
    print("  2. Rebuild: npm run build")
    print(f"  3. Commit: git commit -am 'Bump version to {new_version}'")
    print(f"  4. Tag: git tag v{new_version}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/bump_version.py <version>")
        print("Example: python scripts/bump_version.py 0.2.0")
        sys.exit(1)

    bump_version(sys.argv[1])
