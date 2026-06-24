.PHONY: setup lint test backtest paper

setup:
	uv sync --group dev

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

test:
	uv run pytest tests/

backtest:
	uv run trade-baby-trade backtest \
		--config configs/profiles/paper_spy.yaml \
		--catalog tests/fixtures/catalog

backtest-btc:
	uv run trade-baby-trade backtest \
		--config configs/profiles/backtest_btc.yaml \
		--catalog tests/fixtures/catalog_deribit

paper:
	uv run trade-baby-trade paper \
		--config configs/profiles/paper_spy.yaml
