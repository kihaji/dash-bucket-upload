"""Hatchling build hook: build the JS bundle inside `uv build` / `python -m build`.

The webpack bundle is not git-tracked — wheels are self-building. Requires Node 20+
and npm on PATH when building wheels (PyPI users install prebuilt wheels and never
need Node).

Skip rules:
- sdist builds never run npm (the sdist ships JS sources, not the bundle)
- editable installs (`uv sync`, `pip install -e .`) build only when the bundle is
  missing, so day-to-day syncs stay fast
- DASH_BUCKET_UPLOAD_SKIP_JS_BUILD=1 skips unconditionally (escape hatch for CI
  stages that build the bundle themselves)
"""
import os
import shutil
import subprocess

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

BUNDLE = os.path.join('dash_bucket_upload', 'dash_bucket_upload.min.js')


class JSBuildHook(BuildHookInterface):
    PLUGIN_NAME = 'custom'

    def initialize(self, version, build_data):
        if self.target_name == 'sdist':
            return
        bundle_path = os.path.join(self.root, BUNDLE)
        if os.environ.get('DASH_BUCKET_UPLOAD_SKIP_JS_BUILD'):
            return
        # hatchling signals editable installs via `version` ('standard' | 'editable')
        if version == 'editable' and os.path.exists(bundle_path):
            return

        npm = shutil.which('npm')
        if npm is None:
            if os.path.exists(bundle_path):
                return  # pre-built bundle present; ship it as-is
            raise RuntimeError(
                'Building dash-bucket-upload from source requires Node.js 20+ and npm to compile '
                'the JS bundle (npm ci && npm run build:js). Install Node or install a prebuilt '
                'wheel from PyPI instead.'
            )
        # Note: no NODE_ENV=production here — npm ci would omit devDependencies,
        # and webpack itself is a devDependency.
        subprocess.run([npm, 'ci'], cwd = self.root, check = True)
        subprocess.run([npm, 'run', 'build:js'], cwd = self.root, check = True)
        if not os.path.exists(bundle_path):
            raise RuntimeError(f'JS build completed but {BUNDLE} was not produced')
