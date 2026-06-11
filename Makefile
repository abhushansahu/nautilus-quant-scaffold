.PHONY: setup lint format typecheck test test-unit backtest-smoke report clean

setup:
	uv sync --all-groups

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck:
	uv run mypy src

test:
	uv run pytest

test-unit:
	uv run pytest -m "not integration"

backtest-smoke:
	uv run tbt-backtest run --config config/strategies/ema_cross_demo.yaml --env backtest

report:
	uv run tbt-report latest

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
