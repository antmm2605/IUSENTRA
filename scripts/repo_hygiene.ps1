param(
    [string]$RemoteName = "origin",
    [string[]]$AllowedBranches = @(
        "Codex/legal-electronic-filing-kIxcV",
        "claude/legal-electronic-filing-kIxcV"
    ),
    [switch]$DeleteRemoteExtras
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

$repoRoot = (git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
    throw "Repository root non trovato."
}

Set-Location $repoRoot

$currentBranch = (git branch --show-current).Trim()
if (-not $currentBranch) {
    throw "HEAD detached non supportato: esegui lo script da uno dei branch ammessi."
}

if ($AllowedBranches -notcontains $currentBranch) {
    throw "Branch corrente non ammesso: $currentBranch"
}

Write-Host "== Repo root ==" -ForegroundColor Cyan
Write-Host $repoRoot

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

Write-Host "`n== Rimuove branch locali extra ==" -ForegroundColor Cyan
$localBranches = git for-each-ref --format="%(refname:short)" refs/heads
foreach ($branch in $localBranches) {
    $name = $branch.Trim()
    if (-not $name) { continue }
    if ($AllowedBranches -contains $name) { continue }
    Write-Host "Elimino branch locale: $name"
    Invoke-Git branch -D $name
}

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
        Write-Host "Elimino branch remoto: $shortName"
        Invoke-Git push $RemoteName --delete $shortName
    }
    Invoke-Git fetch --prune $RemoteName
}

Write-Host "`n== Stato finale ==" -ForegroundColor Cyan
Invoke-Git worktree list
Invoke-Git branch --all --verbose --no-abbrev
