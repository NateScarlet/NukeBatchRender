.PHONY: build

export PYTHONPATH=lib

build: 
	uv run python -m PyInstaller -F main.spec
