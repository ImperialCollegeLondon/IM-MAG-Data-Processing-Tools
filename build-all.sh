#!/bin/bash
set -e

OUTPUT_DIR="dist"

rm -rf $OUTPUT_DIR
mkdir "$OUTPUT_DIR"

# iterate over an array of python versions and build each one
for version in 3.9 3.10 3.11 3.12
do
    # apply the version to the current shell
    pyenv local $version
    poetry env use python$version

    # build it
    bash build.sh
    bash pack.sh
done

