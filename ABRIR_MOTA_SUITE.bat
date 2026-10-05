@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Mota Business Suite

set "PYEXE="
set "MODE=%~1"
set "MOTA_PORT=5000"

REM ==========================================================
REM LOCALIZAR PYTHON REAL
REM ==========================================================

for /f "delims=" %%P in ('where python.exe 2^>nul') do (
  echo %%P | findstr /i "WindowsApps" >nul
  if errorlevel 1 (
    if exist "%%P" (
      set "PYEXE=%%P"
      goto :PY_FOUND
    )
  )
)

for %%V in (313 312 311 310) do (
  if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" (
    set "PYEXE=%LocalAppData%\Programs\Python\Python%%V\python.exe"
    goto :PY_FOUND
  )
)

goto :NO_PYTHON

:PY_FOUND

"%PYEXE%" -m pip --version >nul 2>&1
if errorlevel 1 (
  "%PYEXE%" -m ensurepip --upgrade
)

"%PYEXE%" -c "import flask, waitress" >nul 2>&1
if errorlevel 1 (
  echo Instalando dependencias...
  "%PYEXE%" -m pip install -r requirements.txt
  if errorlevel 1 goto :INSTALL_ERROR
)

REM ==========================================================
REM MODO LOCAL (PADRAO) OU REDE
REM ==========================================================

set "MOTA_ALLOW_LAN=0"
set "APP_URL=http://127.0.0.1:%MOTA_PORT%"

if /I "%MODE%"=="rede" (
  set "MOTA_ALLOW_LAN=1"

  for /f "delims=" %%T in ('"%PYEXE%" -c "import secrets; print(secrets.token_urlsafe(24))"') do (
    set "MOTA_ACCESS_TOKEN=%%T"
  )

  set "LANIP="

  for /f "delims=" %%I in ('powershell -NoProfile -Command ^
    "$ip=Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue ^| Where-Object {$_.IPAddress -notmatch '^127\.' -and $_.IPAddress -notlike '169.254.*'} ^| Select-Object -First 1 -ExpandProperty IPAddress; if($ip){$ip}"') do (
    set "LANIP=%%I"
  )

  if not defined LANIP set "LANIP=IP_DO_PC"

  set "LAN_URL=http://!LANIP!:%MOTA_PORT%"
  set "APP_URL=http://127.0.0.1:%MOTA_PORT%"

  echo.
  echo ==========================================================
  echo MODO REDE ATIVADO - ACESSO PROTEGIDO
  echo ==========================================================
  echo.
  echo No celular/tablet abra:
  echo.
  echo   !LAN_URL!
  echo.
  echo Codigo de acesso temporario:
  echo.
  echo   !MOTA_ACCESS_TOKEN!
  echo.
  echo O codigo NAO faz parte da URL.
  echo Nao compartilhe o codigo fora da sua rede local.
  echo.
)

REM ==========================================================
REM INICIAR SERVIDOR
REM ==========================================================

start "Mota Business Suite Server" /min cmd /c ""%PYEXE%" "%~dp0app.py""

set /a TRY=0

:WAIT
set /a TRY+=1

powershell -NoProfile -Command ^
  "try { Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:%MOTA_PORT%' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"

if not errorlevel 1 goto :OPEN

if !TRY! GEQ 30 goto :SERVER_ERROR

timeout /t 1 /nobreak >nul
goto :WAIT

:OPEN
start "" "%APP_URL%"
exit /b 0

:NO_PYTHON
echo.
echo Python valido nao encontrado.
echo Instale:
echo   winget install Python.Python.3.12
echo.
pause
exit /b 1

:INSTALL_ERROR
echo.
echo Falha ao instalar dependencias.
pause
exit /b 1

:SERVER_ERROR
echo.
echo O servidor nao respondeu em 30 segundos.
echo Execute manualmente:
echo   "%PYEXE%" app.py
echo.
pause
exit /b 1
