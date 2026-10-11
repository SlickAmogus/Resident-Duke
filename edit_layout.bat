@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 edit_layout.py %*
goto result
:python
python edit_layout.py %*
:result
if not "%errorlevel%"=="0" pause
