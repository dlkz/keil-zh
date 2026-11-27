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
echo 正在还原英文原版 Keil uVision（从 UV4.exe.bak 恢复）……
echo.
if not exist build mkdir build
"%PYEXE%" "build_patch.py" --restore %* > "build\restore.log" 2>&1
set "RC=%ERRORLEVEL%"
powershell -NoProfile -Command "Get-Content -LiteralPath 'build\restore.log' -Encoding UTF8"
echo.
if "%RC%"=="0" (
  echo [完成] 已还原英文。如需再次汉化，双击根目录「一键安装汉化.bat」。
) else (
  echo [失败] 还原失败，退出码 %RC%。完整日志见 build\restore.log
  echo        若提示备份与目标不匹配，请先确认版本；必要时使用 --force。
)
echo.
pause
exit /b %RC%
