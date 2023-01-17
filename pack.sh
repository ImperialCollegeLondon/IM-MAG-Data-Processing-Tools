#!/bin/bash
set -e

#load the python virtual environment
source .venv/bin/activate

# package the module for distribution
poetry version $(poetry version --short)-dev
poetry lock
poetry build
