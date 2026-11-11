@echo off
rem Gestão OKR (MVP local): liga o sistema e abre o navegador.
rem Para desligar, feche esta janela ou aperte Ctrl + C.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente Python nao encontrado em .venv. Veja o README para a instalacao.
  pause
  exit /b 1
)
.venv\Scripts\python manage.py migrate --noinput
start "" http://127.0.0.1:8000
.venv\Scripts\python manage.py runserver 127.0.0.1:8000
