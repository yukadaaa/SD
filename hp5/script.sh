#!/bin/sh

# Get absolute path to the project folder
DIR="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

# Get absolute path to Conda environment
CONDA_ENV_PATH=$(find /home /opt /usr/local /pkgs -type d -name "baseto" 2>/dev/null | head -n 1)

# Check/download weights
bash $DIR/download_weights.sh

# Run programm
screen -dmS odom $CONDA_ENV_PATH/bin/python3 $DIR/main.py