.PHONY: help install install-server install-client \
        dev-server dev-client \
        test-server lint-server \
        build-client clean

help:
	@echo "Agent-Calendar — common dev commands"
	@echo ""
	@echo "  make install         Install both server and client dependencies"
	@echo "  make dev-server      Run FastAPI in reload mode (127.0.0.1:8080)"
	@echo "  make dev-client      Run Electron + Vite dev"
	@echo "  make test-server     Run pytest"
	@echo "  make lint-server     Run ruff check on server/"
	@echo "  make build-client    Build distributables (.dmg / .exe)"
	@echo "  make clean           Remove venvs, node_modules, build artefacts"

install: install-server install-client

install-server:
	cd server && uv sync

install-client:
	cd client && pnpm install

dev-server:
	cd server && uv run uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload

dev-client:
	cd client && pnpm dev

test-server:
	cd server && uv run pytest

lint-server:
	cd server && uv run ruff check .

build-client:
	cd client && pnpm build

clean:
	rm -rf server/.venv server/.pytest_cache server/.ruff_cache server/.mypy_cache
	rm -rf client/node_modules client/dist client/dist-electron client/release
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
