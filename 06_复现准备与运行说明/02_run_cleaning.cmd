@echo off
setlocal
where py >nul 2>&1
if errorlevel 1 (
    python -B "%~dp0reproduce.py" clean
) else (
    py -3.14 -B "%~dp0reproduce.py" clean
)
set "result=%errorlevel%"
echo.
echo EXIT_CODE=%result%
pause
exit /b %result%