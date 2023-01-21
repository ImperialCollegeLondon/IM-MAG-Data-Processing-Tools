#!/bin/bash
set -e

export OUTPUT_DIR="dist"

rm -rf $OUTPUT_DIR
mkdir "$OUTPUT_DIR"

# iterate over an array of python versions and build each one
for version in 3.9 3.10 3.11
do
    # apply the version to the current shell
    pyenv local $version
    poetry env use python$version
    mkdir "$OUTPUT_DIR/py$version"

    # build it
    bash build.sh
    bash pack.sh

    # copy output to a child folver for this version
    find $OUTPUT_DIR/ -maxdepth 1 -type f -name '*' -exec mv {} "$OUTPUT_DIR/py$version" \;
done

