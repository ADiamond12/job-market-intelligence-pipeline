param(
    [switch]$SkipInstall,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $SkipInstall) {
    python -m pip install -r requirements.txt
    python -m pip install -e .
}

if (-not $SkipTests) {
    pytest
}

Write-Host ""
Write-Host "Running first fixture-backed ATS watchlist snapshot"
jobintel run --config config/verification/companies.fixtures.run1.yaml --run-id portfolio-demo-1

Write-Host ""
Write-Host "Running second fixture-backed snapshot with comparable deltas"
jobintel run --config config/verification/companies.fixtures.run2.yaml --run-id portfolio-demo-2

Write-Host ""
Write-Host "Building history report"
jobintel history --config config/verification/companies.fixtures.run2.yaml --run-id portfolio-history --limit 10

Write-Host ""
Write-Host "Open this index first:"
Write-Host "artifacts/verification/20260326/reports/report_index.html"
Write-Host ""
Write-Host "Then inspect:"
Write-Host "artifacts/verification/20260326/reports/market_summary.html"
Write-Host "artifacts/verification/20260326/reports/history_trend_report.md"
Write-Host "artifacts/verification/20260326/manifests/runs/portfolio-demo-2/manifest.json"
