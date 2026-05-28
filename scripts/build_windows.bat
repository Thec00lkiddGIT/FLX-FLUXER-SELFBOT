@echo off
REM Build Windows folder: dist\FLX\
cd /d "%~dp0\.."
python -m pip install -q -r requirements.txt -r requirements-build.txt
python scripts\prepare_icons.py
pyinstaller build\flx.spec --clean --noconfirm
powershell -NoProfile -Command "Compress-Archive -Path 'dist\FLX' -DestinationPath 'dist\FLX-Windows.zip' -Force"
echo.
echo Done.
echo   Folder: dist\FLX\
echo   Zip:    dist\FLX-Windows.zip
