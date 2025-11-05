#!/bin/bash

# Function to recursively find .bin files and execute the mag command
find_and_run_mag() {
    local dir="$1"
    for file in "$dir"/*; do
        if [ -d "$file" ]; then
            find_and_run_mag "$file"  # Recurse into subdirectories
        elif [[ "$file" == *MAGScience*.csv ]]; then
            echo "Processing file: $file"
            mag check-gap $file
        fi
    done
}

# Starting point: check if a directory is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

# Call the function with the provided directory
find_and_run_mag "$1"
