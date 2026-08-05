.PHONY: refresh-data reproduce report verify test

refresh-data:
	uv run environmental-growth refresh-data

reproduce:
	uv run environmental-growth reproduce

report:
	uv run environmental-growth report

verify:
	uv run environmental-growth verify

test:
	uv run pytest
