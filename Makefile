.PHONY: run test lint typecheck check install build clean release

# ── Dev helpers ────────────────────────────────────────────────────────────────

run:
	python -m helm_dashboard

## Run the full local check suite before pushing
check: lint typecheck test
	@echo ""
	@echo "✅  All checks passed — safe to push."

# ── Individual checks ──────────────────────────────────────────────────────────

lint:
	ruff check helm_dashboard/ tests/

typecheck:
	mypy helm_dashboard/

test:
	pytest tests/ -v

# ── Installation ───────────────────────────────────────────────────────────────

install:
	pip install -e ".[dev]"

# ── Build ──────────────────────────────────────────────────────────────────────

## Build standalone binary via PyInstaller (output: dist/h9s)
build:
	pip install pyinstaller -q
	pyinstaller h9s.spec --clean
	@echo ""
	@echo "Binary ready: dist/h9s"

## Build source + wheel distributions
dist:
	pip install build -q
	python -m build

clean:
	rm -rf dist/ build/ __pycache__ .ruff_cache .mypy_cache .pytest_cache
	find . -name "*.pyc" -delete

# ── Release ────────────────────────────────────────────────────────────────────

## Tag and push a new release. Usage: make release VERSION=1.2.3
release:
ifndef VERSION
	$(error VERSION is not set. Usage: make release VERSION=1.2.3)
endif
	@echo "Tagging v$(VERSION)..."
	git tag v$(VERSION)
	git push origin main
	git push origin v$(VERSION)
	@echo ""
	@echo "GitHub Actions will build binaries and create the release."
	@echo "Then run: make formula-sha VERSION=$(VERSION)"

## Update Formula/h9s.rb with the real SHA256 for a released tag
formula-sha:
ifndef VERSION
	$(error VERSION is not set. Usage: make formula-sha VERSION=1.2.3)
endif
	$(eval SHA := $(shell curl -sL https://github.com/razvanbalsan/h9s/archive/refs/tags/v$(VERSION).tar.gz | shasum -a 256 | awk '{print $$1}'))
	@echo "SHA256: $(SHA)"
	sed -i '' \
		-e 's|refs/tags/v[0-9.]*\.tar\.gz|refs/tags/v$(VERSION).tar.gz|' \
		-e 's|sha256 ".*"|sha256 "$(SHA)"|' \
		Formula/h9s.rb
	git add Formula/h9s.rb
	git commit -m "chore: bump Formula to v$(VERSION)"
	git push origin main
	@echo "Formula updated and pushed."
