install:
	uv sync

run:
	uv run -m src 

debug:
	pudb -m src

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
	rm -rf .mypy_cache

debug:
	pudb main.py config.json

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs \
		--check-untyped-defs

lint-strict:
	flake8 .
	mypy . --strict
