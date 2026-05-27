@echo off
REM Build Windows folder: dist\FLX-FLUXER-SELFBOT\
cd /d "%~dp0.."

if not exist .venv-build (
  python -m venv .venv-build
)

call .venv-build\Scripts\activate.bat
python -m pip install -q -U pip
pip install -q -r requirements.txt -r requirements-build.txt
pyinstaller build\flx.spec --clean --noconfirm
powershell -NoProfile -Command "Compress-Archive -Path 'dist\FLX-FLUXER-SELFBOT' -DestinationPath 'dist\FLX-FLUXER-SELFBOT-Windows.zip' -Force"

echo.
echo Done.
echo   Folder: dist\FLX-FLUXER-SELFBOT\
echo   Zip:    dist\FLX-FLUXER-SELFBOT-Windows.zip
