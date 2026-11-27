@echo off
setlocal
chcp 936 >nul
cd /d "%~dp0.."

set "PYEXE=%CD%\tools\python\python.exe"
if exist "python-path.txt" for /f "usebackq delims=" %%I in ("python-path.txt") do set "PYEXE=%%I"

if not exist "%PYEXE%" (
  echo.
  echo [错误] 没有找到 Python：%PYEXE%
  echo        请完整解压仓库，或修正 python-path.txt。
  echo.
  pause
  exit /b 1
)

echo 使用 Python: %PYEXE%
echo 预览模式：检查词库与已安装 UV4.exe 的匹配情况，不修改 UV4.exe……
echo.
if not exist build mkdir build
"%PYEXE%" "build_patch.py" --dry-run %* > "build\preview.log" 2>&1
set "RC=%ERRORLEVEL%"
powershell -NoProfile -Command "Get-Content -LiteralPath 'build\preview.log' -Encoding UTF8"
echo.
echo 诊断日志见 build\preview.log
echo.
pause
exit /b %RC%
