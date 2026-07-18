param(
    [int]$Port = 8508
)

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$url = "http://localhost:$Port"
Start-Process powershell -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-Command", "Start-Sleep -Seconds 2; Start-Process '$url'" -WindowStyle Hidden
python -m streamlit run app.py --server.headless true --server.port $Port --browser.gatherUsageStats false
