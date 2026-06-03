@echo off
title MediDroid Voice System
echo Starting MediDroid Voice Agent...
echo --------------------------------

rem Change to the directory where the script and database are located
cd /d "c:\Users\abdul\Desktop\GEMINI HOME\MediDroid\voice_system"

rem Run the script using the full python path
"C:\Users\abdul\AppData\Local\Miniconda3\python.exe" "agent.py"

if errorlevel 1 (
    echo.
    echo [ERROR] The helper script failed to run.
    pause
)

pause
