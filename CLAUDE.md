# dash-bucket-upload

Dash custom component for large-file uploads into S3-compatible buckets.
PyPI: `dash-bucket-upload`, import: `dash_bucket_upload`, component: `BucketUpload`.

## Architecture

- `src/lib/components/BucketUpload.react.js` — the ONLY file scanned by
  `dash-generate-components`; keep every other JS module outside `components/`.
  Prop JSDoc comments become the generated Python docstrings (react-docgen 5;
  **react-docgen must stay <6** or codegen breaks).
- `src/lib/engine/` — hand-rolled multipart engine: `uploadEngine.js` (token
  pool + batches), `fileUpload.js` (per-file state machine), `transports/`
  (`direct.js` presigned URLs, `relay.js` server route). Pure helpers
  (`partSize.js`, `retry.js`, `speed.js`) are the vitest targets.
- `src/lib/ui/` — presentational dropzone/file list; inline styles only (no
  CSS files) to stay airgap-safe.
- `dash_bucket_upload/manager.py` — `BucketUploadManager` registers Flask
  routes (`create`, `sign-parts`, `part`, `complete`, `abort`) under
  `url_prefix`. Routes are stateless: non-create routes validate the submitted
  key against the config's prefix pattern (`_keys.key_matches`) instead of a
  server-side registry — keep it that way (gunicorn multi-worker safety).
- `dash_bucket_upload/component.py` — hand-written wrapper (snake_case props,
  `manager=` wiring). `BucketUpload.py`, `_imports_.py`, `metadata.json`,
  `package-info.json` are generated — never edit.
- Part-size constants are mirrored in `_keys.py` and `partSize.js`; change both.
- S3 rules the code honors: parts except the last must be ≥5 MiB; ≤10,000
  parts; part size ≤5 GiB. moto enforces these in tests.

## Commands

- `npm run build` — webpack bundle + regenerate Python component classes
- `npm run build:js` / `npm run build:backends` — individually
- `uv sync` — Python env (builds JS via hatch hook only if bundle missing;
  `DASH_BUCKET_UPLOAD_SKIP_JS_BUILD=1` skips)
- `npm test` — vitest; `uv run pytest` — Python suite (in-process moto server;
  no Docker, no network)
- `make quality` — ruff + pyright (run before presenting work)
- `uv build` — self-building wheel (bundle is gitignored, built by
  `hatch_build.py`)

## Testing

- Python suite runs against a `ThreadedMotoServer` by default; set
  `BUCKET_UPLOAD_S3_ENDPOINT` (+ `_ACCESS_KEY`/`_SECRET_KEY`) to run the same
  suite against real MinIO (`examples/docker-compose.minio.yml`).
- Browser smoke test gated by `BUCKET_UPLOAD_BROWSER_TESTS=1` (needs Chrome).
- vitest gotcha: a function returned from a vitest hook is called as teardown —
  always wrap `mock.mockReset()` in braces inside `beforeEach`.

## Style

- Python: 150-char lines, spaces around `=` in kwargs (`foo(bar = 1)`), ruff +
  pyright clean.
- Versions live in pyproject.toml, package.json, package-lock.json, uv.lock,
  and dash_bucket_upload/package-info.json; `scripts/check_versions.py`
  verifies agreement (CI runs it on release tags); bump via
  `scripts/release.py`.
- Release: tag `vX.Y.Z` on main → publish.yml builds and publishes to PyPI via
  OIDC trusted publishing (no tokens).
