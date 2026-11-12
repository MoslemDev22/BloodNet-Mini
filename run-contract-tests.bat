@echo off
cd /d %~dp0
python -m harness.contract_tests --team http://127.0.0.1:8000
pause
