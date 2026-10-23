@echo off
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env (copy .env.example .env & echo Fichier .env cree : renseigne-le puis relance. & exit /b 1)
python run.py
