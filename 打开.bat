@echo off
chcp 936 >nul
setlocal
set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"

echo ============================================================
echo   AI 国漫短片 / 微电影工作室  -  一键打开
echo   项目位置: %PROJ%
echo ============================================================
echo.

echo [1/2] 正在打开项目文件夹 ...
where code >nul 2>nul
if errorlevel 1 goto use_explorer
start "" code "%PROJ%"
echo   -^> 已用 VS Code 打开
goto after_open
:use_explorer
start "" explorer "%PROJ%"
echo   -^> 已用文件资源管理器打开
:after_open

echo [2/2] 可选：生成一次分镜（失败不影响打开）...
where python >nul 2>nul
if errorlevel 1 goto no_python
if not exist "%PROJ%\scripts\build_shotlist.py" goto no_script
set "CFG="
if exist "%PROJ%\configs\demo_short.json" set "CFG=%PROJ%\configs\demo_short.json"
if not defined CFG if exist "%PROJ%\configs\ww2_example.json" set "CFG=%PROJ%\configs\ww2_example.json"
if not defined CFG if exist "%PROJ%\configs\apocalypse_example.json" set "CFG=%PROJ%\configs\apocalypse_example.json"
if not defined CFG goto no_cfg
echo   配置: %CFG%
echo   ------------------------------------------------
python "%PROJ%\scripts\build_shotlist.py" --config "%CFG%"
echo   ------------------------------------------------
echo   生成结束。无论结果如何，文件夹已打开，可放心使用。
goto done
:no_cfg
echo   未找到任何演示配置，跳过生成。
goto done
:no_script
echo   生成脚本不存在（你可能调整过结构），跳过生成。
goto done
:no_python
echo   未检测到 python，跳过生成。装好 Python 3.11+ 后再手动跑。
:done
echo.
echo 完成。完整步骤见 README.md，关掉本窗口即可。
pause
