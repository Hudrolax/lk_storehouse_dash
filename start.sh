#!/bin/bash
source venv/bin/activate
echo "virtualenv is active now."
python main.py
deactivate
echo "virtualenv is deactivated"