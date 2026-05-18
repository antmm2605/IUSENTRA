param(
    [string]$RemoteName = "origin",
    [string[]]$AllowedBranches = @(
        "Codex/legal-electronic-filing-kIxcV",
        "claude/legal-electronic-filing-kIxcV"
    ),
    [string[]]$ProtectedRemoteBranches = @(
        "chore/monorepo-foundation"
    ),
    [switch]$DeleteRemoteExtras
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

    Write-Host "Registro safe.directory git: $normalized"
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
$repoRoot = Get-GitOutput rev-parse --show-toplevel
if (-not $repoRoot) {
    throw "Repository root non trovato."
}

Set-Location $repoRoot

function Install-RepoHooks {
    param(
        [string]$RootPath
    )

    $hooksDir = Join-Path $RootPath ".githooks"
    if (-not (Test-Path $hooksDir)) {
        throw "Directory hook non trovata: $hooksDir"
    }

    $currentHooksPath = Get-GitOutput config --local --get core.hooksPath
    if ($currentHooksPath -eq ".githooks") {
        return
    }

    Write-Host "Configuro core.hooksPath -> .githooks"
    Invoke-Git config --local core.hooksPath .githooks
}

function Remove-GeneratedArtifacts {
    param(
        [string]$RootPath
    )

    Write-Host "`n== Cleanup artefatti locali ==" -ForegroundColor Cyan

    $transientDirs = @(
        ".pytest_cache",
        ".ruff_cache",
        "tmp",
        "intelligence/downloads"
    )
    foreach ($relative in $transientDirs) {
        $target = Join-Path $RootPath $relative
        if (Test-Path $target) {
            Write-Host "Rimuovo directory temporanea: $relative"
            Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    $transientFiles = @(
        "intelligence/local_ai.db",
        "intelligence/giurisprudenza.json",
        "portale/import_log.json",
        "data/portale/import_log.json",
        "pct.zip"
    )
    foreach ($relative in $transientFiles) {
        $target = Join-Path $RootPath $relative
        if (Test-Path $target) {
            Write-Host "Rimuovo file transitorio: $relative"
            Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
        }
    }

    Get-ChildItem -Path $RootPath -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq "__pycache__" -and $_.FullName -notlike "*\.venv\*"
        } |
        ForEach-Object {
            Write-Host "Rimuovo cache Python: $($_.FullName)"
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }

    Get-ChildItem -Path $RootPath -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object {
            ($_.Extension -in ".pyc", ".pyo") -and $_.FullName -notlike "*\.venv\*"
        } |
        ForEach-Object {
            Write-Host "Rimuovo bytecode: $($_.FullName)"
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
        }
}

function Remove-ExtraBranchConfig {
    param(
        [string[]]$AllowedNames
    )

    Write-Host "`n== Rimuove configurazioni branch extra ==" -ForegroundColor Cyan
    $branchKeys = @(git config --local --name-only --get-regexp "^branch\\..+\\.(remote|merge|vscode-merge-base)$" 2>$null)
    $branchSections = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($key in $branchKeys) {
        if ($key -match '^branch\.(.+)\.(remote|merge|vscode-merge-base)$') {
            [void]$branchSections.Add($Matches[1])
        }
    }

    foreach ($section in $branchSections) {
        if ($AllowedNames -contains $section) {
            continue
        }
        Write-Host "Elimino config branch: $section"
        & git config --local --remove-section "branch.$section" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Config branch gia' assente: $section"
        }
    }
}

$currentBranch = Get-GitOutput branch --show-current
if (-not $currentBranch) {
    throw "HEAD detached non supportato: esegui lo script da uno dei branch ammessi."
}

if ($AllowedBranches -notcontains $currentBranch) {
    throw "Branch corrente non ammesso: $currentBranch"
}

Write-Host "== Repo root ==" -ForegroundColor Cyan
Write-Host $repoRoot

Install-RepoHooks -RootPath $repoRoot

Write-Host "`n== Fetch/prune ==" -ForegroundColor Cyan
Invoke-Git fetch --prune $RemoteName

Write-Host "`n== Sync remoti ammessi sull'HEAD corrente ==" -ForegroundColor Cyan
foreach ($branch in $AllowedBranches) {
    Invoke-Git push $RemoteName "HEAD:$branch"
}

Write-Host "`n== Riallinea branch locali ammessi ==" -ForegroundColor Cyan
foreach ($branch in $AllowedBranches) {
    if ($branch -eq $currentBranch) {
        continue
    }
    Invoke-Git branch -f $branch "refs/remotes/$RemoteName/$branch"
}

Write-Host "`n== Rimuove worktree aggiuntivi ==" -ForegroundColor Cyan
$porcelain = git worktree list --porcelain
$worktreePaths = @()
foreach ($line in $porcelain) {
    if ($line -like "worktree *") {
        $worktreePaths += $line.Substring(9).Trim()
    }
}

foreach ($path in $worktreePaths) {
    if ([System.IO.Path]::GetFullPath($path).TrimEnd('\') -ne [System.IO.Path]::GetFullPath($repoRoot).TrimEnd('\')) {
        Write-Host "Rimozione worktree: $path"
        Invoke-Git worktree remove --force $path
    }
}
Invoke-Git worktree prune
Remove-GeneratedArtifacts -RootPath $repoRoot

Write-Host "`n== Rimuove branch locali extra ==" -ForegroundColor Cyan
$localBranches = git for-each-ref --format="%(refname:short)" refs/heads
foreach ($branch in $localBranches) {
    $name = $branch.Trim()
    if (-not $name) { continue }
    if ($AllowedBranches -contains $name) { continue }
    Write-Host "Elimino branch locale: $name"
    Invoke-Git branch -D $name
}
Remove-ExtraBranchConfig -AllowedNames $AllowedBranches

if ($DeleteRemoteExtras) {
    Write-Host "`n== Rimuove branch remoti extra ==" -ForegroundColor Cyan
    $remoteRefs = git for-each-ref --format="%(refname:short)" "refs/remotes/$RemoteName"
    foreach ($ref in $remoteRefs) {
        $name = $ref.Trim()
        if (-not $name) { continue }
        if ($name -eq "$RemoteName/HEAD") { continue }
        if ($name -eq $RemoteName) { continue }
        if (-not $name.StartsWith("$RemoteName/")) { continue }
        $shortName = $name.Substring($RemoteName.Length + 1)
        if ($AllowedBranches -contains $shortName) { continue }
        if ($ProtectedRemoteBranches -contains $shortName) {
            Write-Host "Branch remoto protetto preservato: $shortName"
            continue
        }
        Write-Host "Elimino branch remoto: $shortName"
        Invoke-Git push $RemoteName --delete $shortName
    }
    Invoke-Git fetch --prune $RemoteName
}

Write-Host "`n== Stato finale ==" -ForegroundColor Cyan
Invoke-Git worktree list
Invoke-Git branch --all --verbose --no-abbrev
