git pull origin main
CALL venv\Scripts\activate
python -m pip uninstall -y calibrator
python -m pip install git+https://github.com/PlusF/Calibrator
pause