.PHONY: setup run test bench docker-up docker-down clean

setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

run:
	.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

test:
	.venv/bin/pytest -v tests/

bench:
	.venv/bin/python scripts/benchmark_concurrency.py

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
