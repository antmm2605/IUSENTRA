param([string[]]$AllowedBranches = @("main"), [string]$HookName = "manual", [switch]$Quiet)
# Branch unico dal 13/10/2026: nessun mirroring o modifica di altri riferimenti.
$ErrorActionPreference = "Stop"
Set-Location ([System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..")))
$currentBranch = & git branch --show-current
if ($LASTEXITCODE -ne 0) { throw "Impossibile verificare il branch corrente." }
if (-not $currentBranch) { exit 0 }
$currentBranch = $currentBranch.Trim()
if ($currentBranch -eq "main" -and -not $Quiet) {
    Write-Host "[git][$HookName] branch operativo main; nessun mirroring."
}
