#!/bin/bash

# Source the environment setup script
source ./setup_env.sh

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Clean pip cache and reinstall requirements
echo "Cleaning pip cache and reinstalling requirements..."
pip cache purge
pip uninstall -y moviepy
pip install --no-cache-dir -r requirements.txt

# Run the application
python app.py
