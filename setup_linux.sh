#!/bin/bash

echo "Creating virtual environment"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

echo "Installing packages"

pip install -r requirements.txt

echo "All Done! You can activate environment using command: source .venv/bin/activate"