@echo off
rem Raccoglie di nuovo gli eventi e apre l'app nel browser del computer.
cd /d "%~dp0"
python raccogli.py
start "" http://localhost:8765/
cd app
python -m http.server 8765
