# 一键启动前后端开发服务
# 用法：在项目根目录执行  .\start.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "[1/3] 准备后端虚拟环境..." -ForegroundColor Cyan
$venvPy = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    python -m venv (Join-Path $root "backend\.venv")
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -r (Join-Path $root "backend\requirements.txt")
}

Write-Host "[2/3] 启动后端 (http://127.0.0.1:8000) ..." -ForegroundColor Cyan
Start-Process -FilePath $venvPy `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory (Join-Path $root "backend")

Write-Host "[3/3] 启动前端 (http://localhost:5173) ..." -ForegroundColor Cyan
$frontend = Join-Path $root "frontend"
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Push-Location $frontend; npm install; Pop-Location
}
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory $frontend

Write-Host "`n已启动！请在浏览器打开 http://localhost:5173" -ForegroundColor Green
