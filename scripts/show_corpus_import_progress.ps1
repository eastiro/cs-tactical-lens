$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$resultsPath = Join-Path $root 'data\processed\iem-cologne-major-2026-corpus\import_results.csv'
$totalReady = 135

Write-Host 'IEM Cologne Major 2026 · 全量 Demo 导入进度' -ForegroundColor Cyan
Write-Host ''

try {
    $processes = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.CommandLine -and $_.CommandLine -match 'import_registry_corpus\.py'
    }
    if ($processes) {
        Write-Host '后台导入：正在运行' -ForegroundColor Green
    } else {
        Write-Host '后台导入：当前未运行（可能已完成或已停止）' -ForegroundColor Yellow
    }
} catch {
    Write-Host '后台导入：进程状态无法读取；请以下方完成数为准。' -ForegroundColor Yellow
}

if (-not (Test-Path -LiteralPath $resultsPath)) {
    Write-Host '尚未写出导入结果。' -ForegroundColor Yellow
    exit 0
}

$rows = Import-Csv -LiteralPath $resultsPath
$done = @($rows | Where-Object { $_.status -eq 'parsed_and_validated' })
$failed = @($rows | Where-Object { $_.status -like 'error:*' })
$handled = @($rows | Where-Object { $_.status -eq 'parsed_and_validated' -or $_.status -like 'error:*' })
$remaining = [Math]::Max(0, $totalReady - $handled.Count)

Write-Host ("已完成：{0} / {1}" -f $done.Count, $totalReady) -ForegroundColor Green
Write-Host ("失败待处理：{0}" -f $failed.Count) -ForegroundColor $(if ($failed.Count) { 'Red' } else { 'Gray' })
Write-Host ("尚未处理：{0}" -f $remaining) -ForegroundColor Yellow
Write-Host ''
Write-Host '按地图：' -ForegroundColor Cyan
$rows | Group-Object map | Sort-Object Name | ForEach-Object {
    $ok = @($_.Group | Where-Object { $_.status -eq 'parsed_and_validated' }).Count
    $bad = @($_.Group | Where-Object { $_.status -like 'error:*' }).Count
    Write-Host ("  {0}: 完成 {1}，失败 {2}" -f $_.Name, $ok, $bad)
}

if ($failed.Count) {
    Write-Host ''
    Write-Host '失败条目：' -ForegroundColor Red
    $failed | ForEach-Object { Write-Host ("  {0} / {1} — {2}" -f $_.match_id, $_.map, $_.status) }
}
