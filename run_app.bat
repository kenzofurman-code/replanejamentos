@echo off
title Piemonte - Replanejamento Fisico-Financeiro
echo ========================================================
echo   PIEMONTE - REPLANEJAMENTO FISICO-FINANCEIRO DE OBRAS
echo ========================================================
echo.
echo Iniciando o servidor FastAPI em http://localhost:8000 ...
echo.
"C:\Users\HomePC\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
pause
