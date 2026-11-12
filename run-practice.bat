@echo off
cd /d %~dp0
python -m pip install -r requirements.txt
if errorlevel 1 ( echo Dependency installation failed. & pause & exit /b 1 )
start "BloodNet API" cmd /k "python service\bloodnet_api.py"
timeout /t 2 /nobreak >nul
python -m harness.runner --team http://127.0.0.1:8000 --scenario P-normal --seed 1000
pause
