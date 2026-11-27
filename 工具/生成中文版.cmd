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
echo 即将把已安装的 Keil uVision 5.x 原地汉化为简体中文 ……
echo （原版 UV4.exe 会先备份为 UV4.exe.bak；请先关闭正在运行的 Keil）
echo.
if not exist build mkdir build
"%PYEXE%" "build_patch.py" %* > "build\build.log" 2>&1
set "RC=%ERRORLEVEL%"
powershell -NoProfile -Command "Get-Content -LiteralPath 'build\build.log' -Encoding UTF8"
echo.
if "%RC%"=="0" (
  echo [成功] 汉化完成。照常双击桌面/开始菜单的 Keil 图标即为中文界面。
  echo        英文原版保留在 UV4.exe 旁的 UV4.exe.bak，随时可还原英文。
) else (
  echo [失败] 退出码 %RC%。完整日志见 build\build.log
  echo        请先完全关闭 Keil；若提示权限不足，请右键以管理员身份重试。
)
echo.
pause
exit /b %RC%
