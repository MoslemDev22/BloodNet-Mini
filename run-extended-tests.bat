@echo off
cd /d %~dp0
python tests\extended_contract.py http://127.0.0.1:8000
pause
