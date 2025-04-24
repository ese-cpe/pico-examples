#!/bin/bash

# Set up variables
BUILD_DIR="build"

# Check if build directory exists
if [ -d "$BUILD_DIR" ]; then
    echo "Cleaning existing build directory..."
    #rm -rf "$BUILD_DIR"/*
else
    echo "Creating build directory..."
    mkdir "$BUILD_DIR"
fi

# Change into the build directory
cd "$BUILD_DIR"

# Run CMake with specified board and platform
echo "Running CMake configuration..."
cmake -DPICO_BOARD=pico2 -DPICO_PLATFORM=rp2350 ../

# Compile all examples using make with 4 threads
echo "Building all examples..."
make -j4
