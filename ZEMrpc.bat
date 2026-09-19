@echo off
setlocal

rem Repository location used by this launcher.
for %%I in ("%~dp0.") do set "APP_DIR=%%~fI"
set "PYTHONW=%APP_DIR%\.venv\Scripts\pythonw.exe"

if not exist "%APP_DIR%" (
    echo Project directory not found:
    echo   %APP_DIR%
    pause
    exit /b 1
)

if not exist "%PYTHONW%" (
    echo Virtual environment Python not found:
    echo   %PYTHONW%
    pause
    exit /b 1
)

rem Use START so cmd.exe does not wait for the GUI process to exit.
rem pythonw.exe keeps the application itself free of a console window.
start "" /D "%APP_DIR%" "%PYTHONW%" -m zemrpc.gui.zemrpc_main
exit /b %ERRORLEVEL%
