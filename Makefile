.PHONY: build

export PYTHONPATH=lib

build: 
	poetry run pyinstaller -F main.spec
