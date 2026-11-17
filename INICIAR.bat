@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
:menu
echo.
echo === THE IRON ARCHIVE 2.0 ===
echo 1 - Diagnostico
echo 2 - Criar episodio
echo 3 - Status da fila
echo 4 - Executar proxima etapa
echo 5 - Aprovar job
 echo 6 - Recuperar jobs interrompidos
echo 0 - Sair
set /p "opt=Escolha: "
if "%opt%"=="1" %PY% main.py doctor
if "%opt%"=="2" (
 set /p "title=Titulo: "
 set /p "goal=Objetivo: "
 call %PY% main.py new --title "!title!" --goal "!goal!"
)
if "%opt%"=="3" %PY% main.py status
if "%opt%"=="4" %PY% main.py run --steps 1
if "%opt%"=="5" (
 set /p "job=Numero do job: "
 call %PY% main.py approve --job !job!
)
if "%opt%"=="6" %PY% main.py reset-stale
if "%opt%"=="0" exit /b 0
goto menu
