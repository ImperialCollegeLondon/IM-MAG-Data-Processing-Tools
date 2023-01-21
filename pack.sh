#!/bin/bash
set -e

#load the python virtual environment
source .venv/bin/activate

# you can set version with command "poetry version 1.2.3"
echo "Packing version $(poetry version --short) for $(python3 --version)"
poetry lock
poetry build
