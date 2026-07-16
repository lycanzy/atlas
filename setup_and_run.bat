@echo off
setlocal
title Atlas Setup and Run

echo.
echo ========================================
echo          Atlas Setup and Run
echo ========================================
echo.

set "ROOT_DIR=%~dp0"
if exist "%ROOT_DIR%experiment_app\manage.py" (
    cd /d "%ROOT_DIR%experiment_app"
) else if exist "%ROOT_DIR%manage.py" (
    cd /d "%ROOT_DIR%"
) else (
    echo ERROR: manage.py was not found.
    echo Keep this script in the Atlas project folder.
    goto :failed
)

set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3"
)

if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo ERROR: Python 3 is not installed or is not available in PATH.
    echo Install Python 3.10 or newer from https://www.python.org/downloads/
    echo During installation, select "Add Python to PATH".
    goto :failed
)

echo [1/6] Checking Python...
%PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo ERROR: Atlas requires Python 3.10 or newer.
    goto :failed
)

echo [2/6] Preparing the virtual environment...
set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

rem Virtual environments contain absolute paths and cannot be copied between PCs.
rem Rebuild an incomplete or non-working environment instead of reusing it.
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo The existing virtual environment belongs to another Python installation.
        echo Rebuilding it for this computer...
        rmdir /s /q "%VENV_DIR%"
        if exist "%VENV_DIR%" (
            echo ERROR: The old virtual environment could not be removed.
            echo Close programs using the .venv folder, then run this script again.
            goto :failed
        )
    )
) else if exist "%VENV_DIR%" (
    echo The existing virtual environment is not compatible with Windows.
    echo Rebuilding it for this computer...
    rmdir /s /q "%VENV_DIR%"
    if exist "%VENV_DIR%" (
        echo ERROR: The old virtual environment could not be removed.
        echo Close programs using the .venv folder, then run this script again.
        goto :failed
    )
)

if not exist "%VENV_PY%" (
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto :failed
)

if not exist "%VENV_PY%" (
    echo ERROR: Python could not create the virtual environment.
    goto :failed
)

echo [3/6] Installing dependencies...
"%VENV_PY%" -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 goto :failed
"%VENV_PY%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :failed

echo [4/6] Preparing the database...
"%VENV_PY%" manage.py migrate
if errorlevel 1 goto :failed

echo [5/6] Checking the application...
"%VENV_PY%" manage.py check
if errorlevel 1 goto :failed

"%VENV_PY%" manage.py shell -c "import sys; from django.contrib.auth import get_user_model; sys.exit(0 if get_user_model().objects.filter(is_superuser=True).exists() else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo No administrator account exists yet.
    echo Please create the first administrator account now.
    echo.
    "%VENV_PY%" manage.py createsuperuser
    if errorlevel 1 goto :failed
)

echo [6/6] Starting Atlas...
echo.
echo Atlas is available at http://127.0.0.1:8000/
echo Keep this window open while using Atlas.
echo Press Ctrl+C to stop the server.
echo.

start "" "http://127.0.0.1:8000/"
"%VENV_PY%" manage.py runserver 127.0.0.1:8000
echo.
echo Atlas has stopped.
pause
goto :end

:failed
echo.
echo Atlas setup could not be completed.
echo Review the error above, then run this script again.
pause
exit /b 1

:end
endlocal
