# The `mag` command line - IMAP Data Processing Tools

A collection of tools to process IMAP Magnetometer science data, which are 3 dimensional vectors saved in CSV files. Written in python.

## Commands examples

- `mag countdown` - How long untill IMAP launch?
- `mag check-gap sample-data/MAGScience-normal-(2,2)-1s-20230922-11h50.csv` - list all gaps in timestamps and sequence counters in science data csv file. Will try and detect packet/vector rates automatically
- `mag check-gap sample-data/**.*.csv` - Use glob to match files and then check gaps in each in turn. Will generate a summary report for all files.
- `mag check-gap --mode normalE8 folder/burst_data20230112-11h23-bad-time-fine.csv` - list all gaps in timestamps and sequence counters in science data csv file and forces the mode to be normalE8
- `mag check-gap --no-report sample-data/MAGScience-normal-(2,2)-1s-20230922-11h50.csv` - list all gaps but skip report generation
- `mag split-packets --limit 100 data/file.bin` - split the first 100 MAG packets in file.bin into individual files in folders based on apid
- `mag split-packets --limit 100 --all data/file.bin` - split the first 100 packets (spacecraft, mag, other instruments) in file.bin into individual files in folders based on apid
- `mag split-packets --apid 1000 --apid 1001 data/*.bin` - extract all packets with apids 1000 and 1001 from all files in data/*.bin and save them into folders based on apid
- `mag split-packets --summarise --apid 0x3e9 --report packets.csv "tests/data/1001/*.bin` - create a packets.csv file with a summary of all packets with apid 1001 in files matching data/*.bin

## Mag cli `USERS` Quick Start

- Download the wheel/tar from the GitHub Actions build artifacts
- Make sure you have the correct version of python installed. 
- Install pipx (not required but this ensures the tool is installed in it's own environment and dependencies cannot make a mess of your system)
    ```bash
    python3 -m pip install --user pipx
    ```
- [install mag with pipx](https://pypa.github.io/pipx/docs/#pipx-install) or with pip if you must. From a folder that contains the whl file or the gz file install like so:
    ```bash
    pipx install --python python3.10 ./python3.10/mag-[VERSION_HERE]-py3-none-any.whl
    ```
- Run mag commands on the command line to check it installed ok
    ```bash
    mag countdown
    mag --help
    ```

See `install.sh` for a script that does some of this for you if you set some environment variables.

## Mag cli `DEVELOPERS` Quick Start

- install vscode and docker (tested on windows with WSL2 and docker desktop)
- clone the repository
- open the repo in vscode and switch to the dev container (CTRL-P -> Reopen in dev container)
- open a terminal and run `poetry install` to restore dependencies
- run the code within poetry in a virtual environment: `poetry run mag --help`
- or run the code with python3 in a virtual environment: `poetry shell` and `poetry install` to setup env and then `python3 src/main.py countdown`. Just calling `mag countdown` also works because the command is actually installed in the virtual env.
- One click to run the tests and generate coverage: `./build.sh`
- One click to package the app into the /dist folder: `./pack.sh`
- One click to run the tests and package the app across multiple versions of python 3.9, 3.10, 3.11 etc: `./build-all.sh`

## Dev Env Setup In Depth

Open folder in VS Code with Dev Containers.

(if not using devcontainers) install poetry (this is done for you in dev container initialisation)

```
./dev-env-first-time.sh
```

Check install has works

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

## Run the build and the tests

From within the devcontainer (or after you have installed poetry) you can run the build script which will install dependencies and run the tests

```bash
./build.sh
```

You can also run tests using the test tooling "Test Explorer" in VSCode, or by calling the pytest cli:

```
$ pytest

# or run a subset of tests
$ pytest tests/test_main.py
$ pytest -k hello
```

To build for all the versions of python you can run

```bash
./build-all.sh
```

Test reports appear automatically in the github actions report.

Code coverage data is generated on build into the folder `htmlcov` and is uploaded on every Actions build.


## Access different versions of python using UV

List the installed versions

```
uv python list
```

And change to a different version of python easily

```
uv python pin 3.10

poetry env use python3.10
python3 --version
poetry install
poetry run mag hello world


uv python pin 3.11
poetry env use python3.11
python3 --version
poetry install
poetry run mag hello world
```

## Python command line app using Typer

This repo publishes to the `/dist` folder a python wheel (.whl) and tar containing a CLI executable called `demo` that can be installed and run. This app uses the library [typer](https://typer.tiangolo.com/) to produce a user friendly interactive cli.

## Tools - poetry, uv, isort, flake8, black

All these tools are preinstalled in the dev container:

- **Python3** - multiple versions installed and available, managed using uv
- **Poetry** - [tool to manage python dependencies](https://python-poetry.org/), tools and package
- **isort, black and flake8** - configured to lint and tidy up your python code automatically. Executed using ./build.sh and CTRL+SHIFT+B (build in vscode)


## About the developer environment

This repository uses an opinionated setup for a python command line app. It uses modern python tooling to make dev easier. It will

- configures the VS Code IDE for east python3 based development, including testing and linting
- use a docker based development environment with vscode devcontainer
- do package management and python version tooling using Poetry and uv
- continuous integration using GitHub Actions, including ruynning unit tests, calculating code coverage and building tarballs and wheel files for you.

## Continuous Integration with GitHub Actions

The `.github/workflows/ci.yml` define a workflow to run on build and test the CLI against multiple versions of python. Build artifacts are generated and a copy of the cli app is available for download for every build
