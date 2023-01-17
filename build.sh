#!/bin/bash
set -e

#load the python virtual environment
source .venv/bin/activate

# restore dependencies
poetry install

# tidy up fomatting
isort src tests
black src

# check syntax
flake8

# execute unit tests with code coverage
pytest -s --cov-config=.coveragerc --cov=src --cov-append --cov-report=xml --cov-report term-missing --cov-report=html tests

