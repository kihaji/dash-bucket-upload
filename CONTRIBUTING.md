# Contributing

## Setup

Requires Python >= 3.12, Node >= 20, and [uv](https://docs.astral.sh/uv/).

```bash
npm install
npm run build      # webpack bundle + regenerate Dash component classes
uv sync            # creates .venv
```

## Workflow

- JS component/engine code lives in `src/lib/`; only
  `src/lib/components/*.react.js` is scanned by `dash-generate-components`.
- After changing component props, run `npm run build` to regenerate
  `dash_bucket_upload/BucketUpload.py` (generated files are never edited by hand).
- Tests: `npm test` (vitest) and `uv run pytest` (moto-backed, offline).
  Optional: run the same pytest suite against MinIO by setting
  `BUCKET_UPLOAD_S3_ENDPOINT` (see `examples/docker-compose.minio.yml`).
- Quality gate before a PR: `make quality` (ruff + pyright), `npm run lint`.

## Releasing

```bash
uv run python scripts/release.py X.Y.Z   # bumps all version files, builds, commits
git push && git push --tags               # tag vX.Y.Z triggers the PyPI publish workflow
```
