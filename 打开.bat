锘緻echo off
chcp 936 >nul
setlocal
set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"

echo ============================================================
echo   AI 鍥芥极鐭墖 / 寰數褰卞伐浣滃  -  涓€閿墦寮€
echo   椤圭洰浣嶇疆: %PROJ%
echo ============================================================
echo.

echo [1/2] 姝ｅ湪鎵撳紑椤圭洰鏂囦欢澶?...
where code >nul 2>nul
if errorlevel 1 goto use_explorer
start "" code "%PROJ%"
echo   -^> 宸茬敤 VS Code 鎵撳紑
goto after_open
:use_explorer
start "" explorer "%PROJ%"
echo   -^> 宸茬敤鏂囦欢璧勬簮绠＄悊鍣ㄦ墦寮€
:after_open

echo [2/2] 鍙€夛細鐢熸垚涓€娆″垎闀滐紙澶辫触涓嶅奖鍝嶆墦寮€锛?..
where python >nul 2>nul
if errorlevel 1 goto no_python
if not exist "%PROJ%\scripts\build_shotlist.py" goto no_script
set "CFG="
if exist "%PROJ%\configs\demo_short.json" set "CFG=%PROJ%\configs\demo_short.json"
if not defined CFG if exist "%PROJ%\configs\ww2_example.json" set "CFG=%PROJ%\configs\ww2_example.json"
if not defined CFG if exist "%PROJ%\configs\apocalypse_example.json" set "CFG=%PROJ%\configs\apocalypse_example.json"
if not defined CFG goto no_cfg
echo   閰嶇疆: %CFG%
echo   ------------------------------------------------
python "%PROJ%\scripts\build_shotlist.py" --config "%CFG%"
echo   ------------------------------------------------
echo   鐢熸垚缁撴潫銆傛棤璁虹粨鏋滃浣曪紝鏂囦欢澶瑰凡鎵撳紑锛屽彲鏀惧績浣跨敤銆?
goto done
:no_cfg
echo   鏈壘鍒颁换浣曟紨绀洪厤缃紝璺宠繃鐢熸垚銆?
goto done
:no_script
echo   鐢熸垚鑴氭湰涓嶅瓨鍦紙浣犲彲鑳借皟鏁磋繃缁撴瀯锛夛紝璺宠繃鐢熸垚銆?
goto done
:no_python
echo   鏈娴嬪埌 python锛岃烦杩囩敓鎴愩€傝濂?Python 3.11+ 鍚庡啀鎵嬪姩璺戙€?
:done
echo.
echo 瀹屾垚銆傚畬鏁存楠よ README.md锛屽叧鎺夋湰绐楀彛鍗冲彲銆?
pause
