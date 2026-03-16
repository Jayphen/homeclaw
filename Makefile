.PHONY: typecheck lint test test-integration test-record dev dev-bob dev-context dev-setup dev-serve ui-build docker-build docker-push

typecheck:
	pyright

lint:
	ruff check homeclaw tests
	ruff format --check homeclaw tests

test:
	pytest tests/ -m "not integration"

test-integration:
	pytest tests/ -m integration

test-record:
	pytest tests/ -m integration --record

dev:
	homeclaw chat --person alice --workspaces ./workspaces-dev

dev-bob:
	homeclaw chat --person bob --workspaces ./workspaces-dev

dev-context:
	homeclaw chat --person alice --workspaces ./workspaces-dev --dry-run

dev-setup:
	python scripts/setup_dev_fixtures.py

dev-serve:
	homeclaw serve --workspaces ./workspaces-dev --port 8081

ui-build:
	cd ui && npm install && npm run build

docker-build:
	docker build -t homeclaw .

docker-push:
	docker push homeclaw
