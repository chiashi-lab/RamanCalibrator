git pull origin main
CALL venv\Scripts\activate
python -m pip uninstall -y calibrator
python -m pip uninstall -y dataloader
python -m pip install git+https://github.com/chiashi-lab/Calibrator
python -m pip install git+https://github.com/chiashi-lab/DataLoader
python -m pip install numpy pillow matplotlib tkinterdnd2==0.3.0 renishawWiRE==0.1.16
pause