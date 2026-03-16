.PHONY: typecheck lint test dev-setup ui-build docker-build docker-push

typecheck:
	pyright

lint:
	ruff check homeclaw tests
	ruff format --check homeclaw tests

test:
	pytest

dev-setup:
	python scripts/setup_dev_fixtures.py

ui-build:
	cd ui && npm install && npm run build

docker-build:
	docker build -t homeclaw .

docker-push:
	docker push homeclaw
