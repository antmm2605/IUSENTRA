[CmdletBinding()]
param(
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$OutputDirectory = if ($OutputDirectory) { $OutputDirectory } else { Join-Path $repositoryRoot 'artifacts\pst-procedure-backups' }
$archiveRoot = [IO.Path]::GetFullPath($OutputDirectory)
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$archiveName = "polisweb-pst-procedura-$timestamp.zip"
$archivePath = Join-Path $archiveRoot $archiveName
$stageRoot = Join-Path ([IO.Path]::GetTempPath()) ("iusentra-pst-procedura-" + [Guid]::NewGuid().ToString('N'))
$payloadRoot = Join-Path $stageRoot 'payload'
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())

$procedureFiles = @(
    'frontend/src/components/TelematicoSurfacePage.tsx',
    'frontend/src/components/FascicoliPage.tsx',
    'frontend/src/components/FascicoliPage.css',
    'pct/fascicoli.py',
    'pct/polisweb.py',
    'tools/local_signer.py',
    'tools/dist/local_signer.py',
    'tools/build_dist.py',
    'tools/build_local_signer_windows_exe.ps1',
    'tools/installa_local_signer_locale.ps1',
    'tools/check_local_signer_boundaries.py',
    'web/bootstrap/fascicoli_document_routes.py',
    'web/bootstrap/fascicoli_surface_wiring.py',
    'web/bootstrap/portali_acquisizione_routes.py',
    'web/bootstrap/runtime_bundle.py',
    'web/bootstrap/telematico_surface_wiring.py',
    'web/services/fascicoli_runtime.py',
    'web/services/react_fascicoli_bridge.py',
    'web/services/telematico_runtime.py',
    'tests/test_fascicoli.py',
    'tests/test_local_signer.py',
    'tests/test_polisweb.py',
    'tests/test_pst_original_presidio_runtime.py',
    'tests/test_react_shell.py',
    'artifacts/react-migration/polisweb-studio-telematico-end-to-end.md'
)

try {
    New-Item -ItemType Directory -Path $payloadRoot -Force | Out-Null
    foreach ($relativePath in $procedureFiles) {
        $sourcePath = Join-Path $repositoryRoot $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "File procedurale non trovato: $relativePath"
        }
        $destinationPath = Join-Path $payloadRoot $relativePath
        $destinationDirectory = Split-Path -Parent $destinationPath
        New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
        Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
    }

    $manifest = [ordered]@{
        schema = 'iusentra.pst-procedure-backup.v1'
        created_at = (Get-Date).ToString('dd/MM/yyyy HH:mm')
        timezone = 'Europe/Rome'
        source_root = $repositoryRoot
        data_included = $false
        notes = 'Solo codice, test e documentazione della procedura PST/PolisWeb. Nessun fascicolo, documento, PIN, certificato o dato di studio è incluso.'
        files = @(
            foreach ($relativePath in $procedureFiles) {
                $sourcePath = Join-Path $repositoryRoot $relativePath
                $hash = Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256
                [ordered]@{
                    path = $relativePath.Replace('\', '/')
                    sha256 = $hash.Hash.ToLowerInvariant()
                    bytes = (Get-Item -LiteralPath $sourcePath).Length
                }
            }
        )
    }
    $manifestPath = Join-Path $payloadRoot 'MANIFEST.json'
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding utf8
    New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
    Compress-Archive -LiteralPath $payloadRoot -DestinationPath $archivePath -CompressionLevel Optimal
    $archiveHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [PSCustomObject]@{
        archive = $archivePath
        sha256 = $archiveHash
        files = $procedureFiles.Count
        data_included = $false
    } | ConvertTo-Json -Compress
}
finally {
    $resolvedStageRoot = [IO.Path]::GetFullPath($stageRoot)
    if ($resolvedStageRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedStageRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
