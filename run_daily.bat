@echo off
REM 한국증시 수급 브리핑 - 매일 실행 배치 (윈도우 작업 스케줄러가 호출)
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ================================================== >> "reports\run.log"
echo [%date% %time%] run start >> "reports\run.log"
".venv\Scripts\python.exe" main.py >> "reports\run.log" 2>&1
echo [%date% %time%] run end (exit=%errorlevel%) >> "reports\run.log"
