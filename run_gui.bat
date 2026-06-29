@echo off
call conda activate aws-env
python "%~dp0gui\app.py"
