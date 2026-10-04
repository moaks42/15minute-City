# Kompas – run, develop and clean up.  `make` lists the targets.
# Works on Linux and macOS (needs make, node/npm, uv, lsof).

ENGINE_PORT ?= 8000
WEB_PORT    ?= 5173
API_URL     := http://localhost:$(ENGINE_PORT)

# Prefer uv; fall back to the engine's existing virtualenv.
PY := $(shell command -v uv >/dev/null 2>&1 && echo "uv run python" || echo ".venv/bin/python")

.DEFAULT_GOAL := help
.PHONY: help install run dev engine web stop check clean

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-8s %s\n", $$1, $$2}'

install: ## Install web and engine dependencies (after clone or pull)
	cd web && npm install
	cd engine && uv sync

run: stop ## Full app on real data: engine + web (Ctrl+C stops both)
	@echo "→ engine $(API_URL)   web http://localhost:$(WEB_PORT)"
	@(cd engine && exec $(PY) -m uvicorn app.main:app --port $(ENGINE_PORT)) & \
	  trap '$(MAKE) -s stop' EXIT; \
	  until curl -sf $(API_URL)/api/health >/dev/null; do sleep 1; done; \
	  cd web && VITE_USE_FIXTURES=0 VITE_API_URL=$(API_URL) npx vite --port $(WEB_PORT) --strictPort

dev: stop ## Web only on sample data (small map, no engine)
	cd web && VITE_USE_FIXTURES=1 npx vite --port $(WEB_PORT) --strictPort

engine: ## Engine only (port 8000)
	cd engine && $(PY) -m uvicorn app.main:app --reload --port $(ENGINE_PORT)

web: ## Web only, pointed at an already running engine
	cd web && VITE_USE_FIXTURES=0 VITE_API_URL=$(API_URL) npx vite --port $(WEB_PORT) --strictPort

stop: ## Kill whatever is listening on the engine/web ports
	@for p in $(ENGINE_PORT) $(WEB_PORT); do \
	  pids=$$(lsof -ti tcp:$$p -sTCP:LISTEN 2>/dev/null); \
	  if [ -n "$$pids" ]; then echo "stopping port $$p ($$pids)"; kill $$pids; fi; \
	done; true

check: ## Before push: locales, build, lint, engine tests
	cd web && npm run build && npm run lint
	cd engine && uv run pytest -q

clean: stop ## Stop servers and delete caches and build output
	rm -rf web/dist web/node_modules/.vite web/node_modules/.vite-temp web/test-results web/playwright-report
	find engine -path engine/.venv -prune -o -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf engine/.pytest_cache
