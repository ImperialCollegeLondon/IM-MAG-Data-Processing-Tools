#!/bin/bash
set -e

# what version is this?
python3 --version

# restore dependencies
poetry install

# load the python virtual environment
source .venv/bin/activate

# tidy up fomatting
poetry run isort src tests
poetry run black src

# check syntax
poetry run flake8

# execute unit tests with code coverage
poetry run pytest -s --cov-config=.coveragerc --cov=src --cov-append --cov-report=xml --cov-report term-missing --cov-report=html --junitxml=test-results.xml tests


