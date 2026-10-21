install:
	uv sync

run:
	uv run python -m src index --max_chunk_size 2000

debug:
	pudb -m src

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
	rm -rf .mypy_cache

lint:
	flake8 src
	mypy src --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs \
		--check-untyped-defs

lint-strict:
	flake8 src
	mypy src --strict
