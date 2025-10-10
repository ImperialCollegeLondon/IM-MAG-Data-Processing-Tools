#!/bin/bash
set -e

OUTPUT_DIR="dist"

rm -rf $OUTPUT_DIR
mkdir "$OUTPUT_DIR"

# iterate over an array of python versions and build each one
for version in 3.10 3.11 3.12 3.13 3.14;
do
    # apply the version to the current shell
    uv python pin $version

    printf "\n\nBuilding for Python %s\n\n" "$version"

    poetry env use python$version

    # build it
    bash build.sh
    bash pack.sh
done

