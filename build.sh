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

# execute unit tests
pytest

