# Makefile for dash-bucket-upload
#
# Usage:
#   make          - Build minified production version
#   make dev      - Build non-minified development version
#   make clean    - Remove build artifacts
#   make release VERSION=x.y.z - Verify clean tree + version consistency and tag for release
#   make check-versions [VERSION=x.y.z] - Verify all version sources agree (and match VERSION if given)
#   make docs      - Build the docs site (strict)
#   make docs-serve - Serve the docs with live reload
#


# Default target - build production version
all: build

# Build minified production version
build:
	@echo "Building production (minified) version..."
	npm run build:js
	@echo "Build complete: dash_bucket_upload/dash_bucket_upload.min.js"

# Build development (non-minified) version
dev:
	@echo "Building development (non-minified) version..."
	npm run build:js -- --mode development
	@echo "Build complete: dash_bucket_upload/dash_bucket_upload.dev.js"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -f dash_bucket_upload/dash_bucket_upload.min.js
	rm -f dash_bucket_upload/dash_bucket_upload.min.js.map
	rm -f dash_bucket_upload/dash_bucket_upload.min.js.LICENSE.txt
	rm -f dash_bucket_upload/dash_bucket_upload.dev.js
	rm -f dash_bucket_upload/dash_bucket_upload.dev.js.map
	@echo "Clean complete"

# Run code quality checks: ruff (lint) + Pyright (types)
quality:
	@echo "Running ruff linter..."
	uv run ruff check .
	@echo "Running Pyright type checker..."
	uv run npx pyright
	@echo ""
	@echo "Quality check complete."

.PHONY: docs docs-serve

# Build the documentation site strictly (as CI does) into site/
docs:
	uv run --only-group docs mkdocs build --strict

# Serve the documentation with live reload at http://127.0.0.1:8000
docs-serve:
	uv run --only-group docs mkdocs serve

# Check if git working directory is clean
check-git:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory has uncommitted changes:"; \
		git status --short; \
		echo ""; \
		echo "Please commit or stash changes before releasing."; \
		exit 1; \
	fi
	@echo "Git working directory is clean"

# Check that VERSION is provided
check-version:
	@if [ -z "$(VERSION)" ]; then \
		echo "Error: VERSION is required"; \
		echo "Usage: make release VERSION=x.y.z"; \
		exit 1; \
	fi
	@echo "Release version: $(VERSION)"

# Check that all version sources agree (and match VERSION when provided)
check-versions:
	uv run python scripts/check_versions.py $(VERSION)

# Release target - verify clean tree + version consistency and tag
# Run "make build" and commit before releasing (or use scripts/release.py to bump + build + commit)
release: check-version check-git check-versions
	@echo ""
	@echo "Creating git tag v$(VERSION)..."
	git tag -a "v$(VERSION)" -m "Release v$(VERSION)"
	@echo ""
	@echo "=========================================="
	@echo "Release v$(VERSION) prepared successfully!"
	@echo "=========================================="
	@echo ""
	@echo "To publish, run:"
	@echo "  git push && git push --tags"
	@echo ""
