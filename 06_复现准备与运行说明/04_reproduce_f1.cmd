@echo off
setlocal
where py >nul 2>&1
if errorlevel 1 (
    python -B "%~dp0reproduce.py" f1
) else (
    py -3.14 -B "%~dp0reproduce.py" f1
)
set "result=%errorlevel%"
echo.
echo EXIT_CODE=%result%
pause
exit /b %result%