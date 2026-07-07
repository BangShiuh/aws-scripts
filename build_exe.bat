@echo off
setlocal

echo === EC2 Manager — Build Standalone Executable ===
echo.

call conda activate aws-env 2>nul
if errorlevel 1 (
    echo ERROR: Could not activate the aws-env conda environment.
    echo Make sure Miniconda is installed and you have run:
    echo   conda env create -f ec2\environment.yaml
    pause
    exit /b 1
)

echo Cleaning previous build...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

echo.
echo Building (this takes 1-3 minutes)...
pyinstaller --clean ec2_manager.spec

if errorlevel 1 (
    echo.
    echo Build FAILED. See output above for details.
    pause
    exit /b 1
)

echo.
echo ==============================================
echo  Build complete!
echo  Executable: dist\EC2 Manager.exe
echo  Share that single file with your students.
echo ==============================================
pause
