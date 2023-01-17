# IM-MAG-Data-Processing-Tools

A collection of tools to process IMAP Magnetometer science data, which are 3 dimensional vectors saved in CSV files. Written in python.

## Install and run tool

```
python3 src/main.py hello mag
```

or via poetry to ensure clean dependecies:

```
poetry run mag hello world
```

or manually using poetry:

```
poetry run python3 src/main.py hello world
```

## Developer Quick start

Open folder in VS Code with Dev Containers.

install poetry (done for you in dev container init is using vscode)

```
./first-time.sh
```

Check it works

```
$ poetry --version
Poetry (version 1.3.2)

# also you can update it
$ poetry self update
```

Then start a shell (this creates a virtual env for you automatically) with the tools we need available. vscode does this automagically when you spawn  a terminal.

```
$ poetry shell
```

Restore dependencies

```
$ poetry install
```

and now you can run tools such as

```
pytest
flake8
black src
```

## Run the full build

From within the devcontainer (or after you have installed poetry)

$ ./build.sh


## Run some tests

Either use the test runner in vscode (with debugging)

Or on the cli using pytest

```
$ pytest

# or a subset of tests
$ pytest tests/test_main.py
$ pytest -k hello
```

