#!/usr/bin/env python3
"""Fail if a mkdocstrings `::: path` directive in docs/ renders nothing useful.

`mkdocs build --strict` happily renders an object with no docstring as an empty
section; e.g. `dash_bucket_upload.BucketUpload` statically resolves to the
generated BucketUpload.py module, not the class. This catches that: every
directive must resolve to a class or function that has a docstring.
"""
import re
import sys
from pathlib import Path

import griffe

ROOT = Path(__file__).parent.parent
DIRECTIVE = re.compile(r'^:::\s+(\S+)', re.MULTILINE)


def main() -> int:
    package = griffe.load('dash_bucket_upload', search_paths = [str(ROOT)])
    errors = []
    for md in sorted((ROOT / 'docs').rglob('*.md')):
        for path in DIRECTIVE.findall(md.read_text()):
            rel = md.relative_to(ROOT)
            try:
                obj = package[path.removeprefix('dash_bucket_upload.')]
            except KeyError:
                errors.append(f'{rel}: {path} does not exist')
                continue
            if obj.is_alias:
                obj = obj.final_target
            if obj.kind.value not in ('class', 'function'):
                errors.append(f'{rel}: {path} resolves to a {obj.kind.value} ({obj.path}), not a class or function')
            elif not obj.docstring:
                errors.append(f'{rel}: {path} has no docstring')
    for error in errors:
        print(f'error: {error}', file = sys.stderr)
    if not errors:
        print('docs API directives OK')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
