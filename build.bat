@echo off
rem Builds the release:  dist\PhoneLink.exe  (single file)  and  release\PhoneLink-<version>-win64.zip
rem adb + scrcpy-server are bundled from the platform-tools folder one level up.
setlocal
cd /d "%~dp0"
set PT=%~dp0..
set PY=.venv\Scripts\python

if not exist %PY%.exe (
  py -m venv .venv || exit /b 1
  %PY% -m pip install -r requirements.txt || exit /b 1
)

%PY% -m pytest -q || exit /b 1
%PY% tools\make_icon.py || exit /b 1

%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name PhoneLink ^
  --icon assets\phonelink.ico ^
  --version-file tools\version_info.txt ^
  --add-binary "%PT%\adb.exe;." ^
  --add-binary "%PT%\AdbWinApi.dll;." ^
  --add-binary "%PT%\AdbWinUsbApi.dll;." ^
  --add-data "%PT%\scrcpy-server;." ^
  --add-data "docs\USER_GUIDE.md;docs" ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets ^
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick ^
  --exclude-module PySide6.QtSql --exclude-module PySide6.QtCharts ^
  main.py || exit /b 1

for /f "delims=" %%v in ('%PY% -c "import phonelink;print(phonelink.__version__)"') do set VER=%%v
set REL=release\PhoneLink-%VER%-win64
if exist release rmdir /s /q release
mkdir "%REL%\licenses"
copy dist\PhoneLink.exe "%REL%\" >nul
copy docs\USER_GUIDE.md "%REL%\USER_GUIDE.md" >nul
if exist "%PT%\LICENSE.txt" copy "%PT%\LICENSE.txt" "%REL%\licenses\" >nul
if exist "%PT%\NOTICE.txt" copy "%PT%\NOTICE.txt" "%REL%\licenses\platform-tools-NOTICE.txt" >nul
copy THIRD_PARTY_NOTICES.md "%REL%\licenses\" >nul
copy LICENSE "%REL%\licenses\PhoneLink-LICENSE.txt" >nul
powershell -NoProfile -Command "Compress-Archive -Path '%REL%\*' -DestinationPath 'release\PhoneLink-%VER%-win64.zip' -Force"
echo.
echo Built dist\PhoneLink.exe and release\PhoneLink-%VER%-win64.zip
