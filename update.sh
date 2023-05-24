#!/bin/sh
git pull origin main
. venv/bin/activate
pause
python -m pip uninstall calibrator
python -m pip install git+https://github.com/PlusF/Calibrator

