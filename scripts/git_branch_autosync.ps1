param(
    [string[]]$AllowedBranches = @(
        "Codex/legal-electronic-filing-kIxcV",
        "claude/legal-electronic-filing-kIxcV"
    ),
    [string]$HookName = "manual",
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-SafeDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoPath
    )

    $normalized = [System.IO.Path]::GetFullPath($RepoPath).TrimEnd('\')
    $safeDirectories = @(git config --global --get-all safe.directory 2>$null)
    foreach ($entry in $safeDirectories) {
        $candidate = $entry.Trim()
        if (-not $candidate) {
            continue
        }
        if ($candidate -eq "*") {
            return
        }
        try {
            if ([System.IO.Path]::GetFullPath($candidate).TrimEnd('\') -eq $normalized) {
                return
            }
        }
        catch {
            if ($candidate.TrimEnd('\') -eq $normalized) {
                return
            }
        }
    }

    & git config --global --add safe.directory $normalized
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git config --global --add safe.directory $normalized"
    }
}

function Invoke-Git {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($Args -join ' ')"
    }
}

function Get-GitOutput {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )

    $output = & git @Args 2>$null
    if ($null -eq $output) {
        return ""
    }
    return ($output -join "`n").Trim()
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
Ensure-SafeDirectory -RepoPath $repoRoot
Set-Location $repoRoot

$currentBranch = Get-GitOutput branch --show-current
if (-not $currentBranch) {
    exit 0
}
if ($AllowedBranches -notcontains $currentBranch) {
    exit 0
}

$currentHead = Get-GitOutput rev-parse HEAD
if (-not $currentHead) {
    exit 0
}

$updatedBranches = [System.Collections.Generic.List[string]]::new()
foreach ($branch in $AllowedBranches) {
    if ($branch -eq $currentBranch) {
        continue
    }

    $existingHead = Get-GitOutput rev-parse --verify "refs/heads/$branch"
    if ($existingHead -eq $currentHead) {
        continue
    }

    Invoke-Git branch -f $branch $currentHead
    if (-not (Get-GitOutput config --local --get "branch.$branch.remote")) {
        Invoke-Git config --local "branch.$branch.remote" origin
    }
    if (-not (Get-GitOutput config --local --get "branch.$branch.merge")) {
        Invoke-Git config --local "branch.$branch.merge" "refs/heads/$branch"
    }
    $updatedBranches.Add($branch) | Out-Null
}

if (-not $Quiet -and $updatedBranches.Count -gt 0) {
    Write-Host "[git autosync][$HookName] branch locali riallineati: $($updatedBranches -join ', ')" -ForegroundColor DarkCyan
}
