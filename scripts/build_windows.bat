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

echo.
echo Done. Run:
echo   dist\FLX-FLUXER-SELFBOT\FLX-FLUXER-SELFBOT.exe
