#!/bin/bash
set -e

MAG_PYTHON_VERSION="${MAG_PYTHON_VERSION:-python3.11}"
MAG_PACKAGE="${MAG_PACKAGE:-mag-*.tar.gz}"

if [ ! -f dist/$MAG_PYTHON_VERSION/$MAG_PACKAGE ]
then
    echo "Cannot find tar in dist/$MAG_PYTHON_VERSION. Run build-all.sh?"
    exit 1
fi

# install using pipx for nice clean isolation
python3 -m pip install --user pipx

# use the tar file in the dist folder (assumes you already ran build-all.sh) to install the mag CLI as a global tool
pipx install --python $MAG_PYTHON_VERSION dist/$MAG_PYTHON_VERSION/$MAG_PACKAGE

# (Optional) Check it worked?
# mag --help

# (Optional) uninstall
# pipx uninstall mag
