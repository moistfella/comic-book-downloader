@echo off
title Updater - Comic Book Downloader
echo Checking prerequisites...

where git >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Git is not installed or not in PATH.
    echo Please install Git from https://git-scm.com/install/windows
    pause
    exit /b 1
)

if not exist ".git" (
    echo Error: Not a Git repository.
    pause
    exit /b 1
)

echo Pulling latest changes from GitHub...
git pull
if %ERRORLEVEL% equ 0 (
    echo.
    echo Update complete!
    echo Enjoy using the new version of Comic Book Downloader!
    echo.
) else (
    echo.
    echo Update failed. Please check the error message above.
    echo.
)
pause
