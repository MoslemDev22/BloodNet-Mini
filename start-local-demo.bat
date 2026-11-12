@echo off
cd /d %~dp0
start "BloodNet Gateway" cmd /k "python -m harness.mock_gateway --port 9100"
start "BloodNet Travel" cmd /k "python -m harness.travel_service --port 9200"
start "BloodNet Inventory" cmd /k "python -m harness.inventory_service --port 9300 --kit participant_kit"
timeout /t 2 /nobreak >nul
start "BloodNet API" cmd /k "python service\bloodnet_api.py"
start "BloodNet Web UI" cmd /k "python -m http.server 8080 --directory web"
echo.
echo BloodNet local demo is starting.
echo API: http://127.0.0.1:8000/health
echo UI:  http://127.0.0.1:8080
echo Demo tokens are documented in README.md.
echo Close all five terminal windows to stop the services.
pause
