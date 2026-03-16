.PHONY: typecheck lint test ui-build docker-build docker-push

typecheck:
	pyright

lint:
	ruff check homeclaw tests
	ruff format --check homeclaw tests

test:
	pytest

ui-build:
	cd ui && npm install && npm run build

docker-build:
	docker build -t homeclaw .

docker-push:
	docker push homeclaw
