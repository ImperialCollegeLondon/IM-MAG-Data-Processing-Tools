#!/bin/bash
set -e

# what version is this?
poetry run python --version

# restore dependencies
poetry install -q

# load the python virtual environment
source .venv/bin/activate

# tidy up fomatting
poetry run isort src tests
poetry run black src

# check syntax
poetry run flake8

# execute unit tests with code coverage
poetry run pytest -rP -v --cov-config=.coveragerc --cov=src --cov-append --cov-report=xml --cov-report term-missing --cov-report=html --junitxml=test-results.xml tests


