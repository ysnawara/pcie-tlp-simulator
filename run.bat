@echo off
echo ========================================
echo  PCIe Bus Simulator
echo ========================================
echo.
echo Installing dependencies...
pip install rich pytest customtkinter --quiet 2>nul
echo.
echo Launching GUI...
python main.py
