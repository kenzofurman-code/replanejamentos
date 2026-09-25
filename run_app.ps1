Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  PIEMONTE - REPLANEJAMENTO FISICO-FINANCEIRO DE OBRAS" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Iniciando o servidor FastAPI em http://localhost:8000 ..." -ForegroundColor Green
Write-Host ""

& "C:\Users\HomePC\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
