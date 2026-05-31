param(
    [string]$CartellaStudioTelematico = "C:\QuickOrganizer",
    [string]$Destinazione = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

function Restart-InPowerShell32 {
    $windir = $env:WINDIR
    if (-not $windir) { $windir = "C:\Windows" }
    $ps32 = Join-Path $windir "SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
    if ((Test-Path $ps32) -and [Environment]::Is64BitProcess) {
        $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath, "-CartellaStudioTelematico", $CartellaStudioTelematico)
        if ($Destinazione) { $args += @("-Destinazione", $Destinazione) }
        & $ps32 @args
        exit $LASTEXITCODE
    }
}

Restart-InPowerShell32

function Test-StudioTelematicoRoot {
    param([string]$Path)
    if (-not $Path) { return $false }
    $resolved = [System.IO.Path]::GetFullPath($Path)
    return (
        (Test-Path (Join-Path $resolved "QuickOrganizer.mdb")) -and
        (Test-Path (Join-Path $resolved "ATTI")) -and
        (Test-Path (Join-Path $resolved "EMAILS"))
    )
}

function Resolve-StudioTelematicoRootCandidate {
    param([string]$Path)
    if (-not $Path) { return $null }
    try {
        $resolved = [System.IO.Path]::GetFullPath($Path)
    } catch {
        return $null
    }
    if (Test-StudioTelematicoRoot $resolved) {
        return $resolved
    }
    $leaf = Split-Path -Leaf $resolved
    $parent = Split-Path -Parent $resolved
    if ($parent -and ($leaf -in @("ATTI", "EMAILS")) -and (Test-StudioTelematicoRoot $parent)) {
        return [System.IO.Path]::GetFullPath($parent)
    }
    if ($parent -and (Test-StudioTelematicoRoot $parent)) {
        return [System.IO.Path]::GetFullPath($parent)
    }
    return $null
}

function Select-StudioTelematicoRoot {
    param([string]$InitialPath)
    $candidates = @(
        $InitialPath,
        "C:\QuickOrganizer",
        "C:\StudioTelematico",
        "C:\ProgramData\QuickOrganizer"
    ) | Where-Object { $_ } | Select-Object -Unique
    foreach ($candidate in $candidates) {
        $resolved = Resolve-StudioTelematicoRootCandidate $candidate
        if ($resolved) {
            return $resolved
        }
    }

    try {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = "Seleziona la cartella Studio Telematico/QuickOrganizer che contiene QuickOrganizer.mdb, ATTI ed EMAILS"
        $dialog.ShowNewFolderButton = $false
        if ($InitialPath -and (Test-Path $InitialPath)) {
            $dialog.SelectedPath = [System.IO.Path]::GetFullPath($InitialPath)
        }
        if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            $resolved = Resolve-StudioTelematicoRootCandidate $dialog.SelectedPath
            if ($resolved) {
                return $resolved
            }
        }
    } catch {
        # Se la scelta grafica non è disponibile, resta il messaggio controllato sotto.
    }

    throw "Seleziona una cartella che contenga QuickOrganizer.mdb, ATTI ed EMAILS."
}

$root = Select-StudioTelematicoRoot -InitialPath $CartellaStudioTelematico
$mdb = Join-Path $root "QuickOrganizer.mdb"
$atti = Join-Path $root "ATTI"
$emails = Join-Path $root "EMAILS"

if (-not (Test-Path $mdb)) {
    throw "Archivio QuickOrganizer.mdb non trovato in $root"
}
if (-not (Test-Path $atti)) {
    throw "Cartella ATTI non trovata in $root"
}
if (-not (Test-Path $emails)) {
    throw "Cartella EMAILS non trovata in $root"
}

if (-not $Destinazione) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $Destinazione = Join-Path $desktop "IUSENTRA-StudioTelematico-$stamp.zip"
}

$tables = @(
    "PRATICHE",
    "NOMI",
    "TAVOLA",
    "TESTI",
    "EMAILS",
    "AGENDA",
    "Parcelle",
    "Prestazioni",
    "PrecisazioneCredito",
    "Titoli",
    "BeniMobili",
    "BeniImmobili",
    "DirittiReali",
    "Ipoteche"
)

$requiredTables = @("PRATICHE", "NOMI", "TAVOLA", "TESTI", "EMAILS", "AGENDA")
$requiredFields = @{
    "PRATICHE" = @("NUMEROPRATICA")
    "NOMI" = @("NUM_NOM", "CONTROLLO")
    "TAVOLA" = @("NUMEROPRATICA", "NUM_NOM")
    "TESTI" = @("NUMEROPRATICA", "NOME_DOS")
    "EMAILS" = @("NumeroPratica", "NOME_DOS")
    "AGENDA" = @("NumeroPratica")
}

$conn = New-Object System.Data.OleDb.OleDbConnection("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$mdb;Persist Security Info=False;")
$payload = [ordered]@{
    format = "iusentra.quickorganizer.v1"
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    source = "Studio Telematico"
    tables = [ordered]@{}
}

$conn.Open()
try {
    foreach ($table in $tables) {
        $cmd = $conn.CreateCommand()
        $cmd.CommandText = "SELECT * FROM [$table]"
        try {
            $reader = $cmd.ExecuteReader()
            $rows = New-Object System.Collections.ArrayList
            while ($reader.Read()) {
                $obj = [ordered]@{}
                for ($i = 0; $i -lt $reader.FieldCount; $i++) {
                    $name = $reader.GetName($i)
                    if ($reader.IsDBNull($i)) {
                        $obj[$name] = $null
                    } else {
                        $value = $reader.GetValue($i)
                        if ($value -is [datetime]) { $obj[$name] = $value.ToString("o") }
                        else { $obj[$name] = $value }
                    }
                }
                [void]$rows.Add($obj)
            }
            $reader.Close()
            $payload.tables[$table] = $rows
        } catch {
            if ($requiredTables -contains $table) {
                throw "Tabella obbligatoria $table non leggibile nel database Studio Telematico: $($_.Exception.Message)"
            }
            $payload.tables[$table] = @()
        }
    }
} finally {
    $conn.Close()
}

function Get-PayloadRows {
    param([string]$TableName)
    if ($payload.tables.Contains($TableName)) {
        return @($payload.tables[$TableName])
    }
    return @()
}

function Test-AnyRowHasField {
    param(
        [object[]]$Rows,
        [string]$FieldName
    )
    foreach ($row in $Rows) {
        if ($row -and $row.Contains($FieldName)) {
            return $true
        }
    }
    return ($Rows.Count -eq 0)
}

$missingFields = New-Object System.Collections.ArrayList
foreach ($entry in $requiredFields.GetEnumerator()) {
    $rows = @(Get-PayloadRows $entry.Key)
    foreach ($field in $entry.Value) {
        if (-not (Test-AnyRowHasField -Rows $rows -FieldName $field)) {
            [void]$missingFields.Add([ordered]@{ table = $entry.Key; field = $field })
        }
    }
}

$tableCounts = [ordered]@{}
foreach ($table in $tables) {
    $tableCounts[$table] = @(Get-PayloadRows $table).Count
}

$nomiById = @{}
foreach ($nominativo in @(Get-PayloadRows "NOMI")) {
    $numNom = [string]$nominativo["NUM_NOM"]
    if ($numNom) {
        $nomiById[$numNom] = $nominativo
    }
}

$matterNumbers = New-Object "System.Collections.Generic.HashSet[string]"
$mattersWithParties = New-Object "System.Collections.Generic.HashSet[string]"
$mattersWithClient = New-Object "System.Collections.Generic.HashSet[string]"
$clientPartyLinks = 0
foreach ($pratica in @(Get-PayloadRows "PRATICHE")) {
    $numeroPratica = [string]$pratica["NUMEROPRATICA"]
    if ($numeroPratica) {
        [void]$matterNumbers.Add($numeroPratica)
        $titolareId = [string]$pratica["TitolareID"]
        if ($titolareId) {
            [void]$mattersWithClient.Add($numeroPratica)
        }
    }
}
foreach ($link in @(Get-PayloadRows "TAVOLA")) {
    $numeroPratica = [string]$link["NUMEROPRATICA"]
    $numNom = [string]$link["NUM_NOM"]
    if ($numeroPratica) {
        [void]$mattersWithParties.Add($numeroPratica)
    }
    $nominativo = $nomiById[$numNom]
    if ($nominativo) {
        $controllo = ([string]$nominativo["CONTROLLO"]).Trim().ToUpperInvariant()
        if ($controllo.StartsWith("CLI") -or $controllo.StartsWith("OWN")) {
            $clientPartyLinks += 1
            if ($numeroPratica) {
                [void]$mattersWithClient.Add($numeroPratica)
            }
        }
    }
}

$payload.validation = [ordered]@{
    table_counts = $tableCounts
    relation_counts = [ordered]@{
        matters = $matterNumbers.Count
        matters_with_parties = $mattersWithParties.Count
        matters_without_parties = [Math]::Max($matterNumbers.Count - $mattersWithParties.Count, 0)
        client_party_links = $clientPartyLinks
        matters_with_client = $mattersWithClient.Count
        matters_without_client = [Math]::Max($matterNumbers.Count - $mattersWithClient.Count, 0)
    }
    missing_required_fields = $missingFields
    can_import_complete = (
        ($missingFields.Count -eq 0) -and
        ($tableCounts["PRATICHE"] -gt 0) -and
        ($tableCounts["NOMI"] -gt 0) -and
        ($tableCounts["TAVOLA"] -gt 0)
    )
}

if (-not $payload.validation.can_import_complete) {
    throw "Archivio dati Studio Telematico incompleto: PRATICHE, NOMI e TAVOLA devono essere presenti con i campi obbligatori. Nessun pacchetto parziale e' stato creato."
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Add-TextEntryToZip {
    param(
        [System.IO.Compression.ZipArchive]$Archive,
        [string]$EntryName,
        [string]$Content
    )
    $entry = $Archive.CreateEntry($EntryName, [System.IO.Compression.CompressionLevel]::Optimal)
    $stream = $entry.Open()
    $encoding = New-Object System.Text.UTF8Encoding($false)
    $writer = New-Object System.IO.StreamWriter($stream, $encoding)
    try {
        $writer.Write($Content)
    } finally {
        $writer.Dispose()
    }
}

function Add-FolderToZip {
    param(
        [System.IO.Compression.ZipArchive]$Archive,
        [string]$SourceFolder,
        [string]$EntryRoot
    )
    if (-not (Test-Path $SourceFolder)) { return }
    $rootFull = [System.IO.Path]::GetFullPath($SourceFolder)
    $files = @(Get-ChildItem -LiteralPath $rootFull -Recurse -File -Force)
    $total = [Math]::Max($files.Count, 1)
    $index = 0
    foreach ($file in $files) {
        $index += 1
        $relative = $file.FullName.Substring($rootFull.Length).TrimStart('\', '/')
        if (-not $relative) { continue }
        $entryName = ($EntryRoot.Trim('\', '/') + "/" + ($relative -replace '\\', '/')).TrimEnd('/')
        $percent = [Math]::Min(99, [Math]::Floor(($index / $total) * 100))
        Write-Progress -Activity "Preparazione pacchetto IUSENTRA" -Status "$EntryRoot $index/$total" -PercentComplete $percent
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $Archive,
            $file.FullName,
            $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
}

if (Test-Path $Destinazione) { Remove-Item -LiteralPath $Destinazione -Force }
$destParent = Split-Path -Parent ([System.IO.Path]::GetFullPath($Destinazione))
if ($destParent -and -not (Test-Path $destParent)) {
    New-Item -ItemType Directory -Path $destParent | Out-Null
}

$json = $payload | ConvertTo-Json -Depth 12
$zipStream = [System.IO.File]::Open($Destinazione, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
$archive = New-Object System.IO.Compression.ZipArchive($zipStream, [System.IO.Compression.ZipArchiveMode]::Create, $false, [System.Text.Encoding]::UTF8)
try {
    Write-Progress -Activity "Preparazione pacchetto IUSENTRA" -Status "Scrivo archivio dati" -PercentComplete 5
    Add-TextEntryToZip -Archive $archive -EntryName "quickorganizer-export.json" -Content $json
    Add-FolderToZip -Archive $archive -SourceFolder $atti -EntryRoot "ATTI"
    Add-FolderToZip -Archive $archive -SourceFolder $emails -EntryRoot "EMAILS"
} finally {
    $archive.Dispose()
    $zipStream.Dispose()
    Write-Progress -Activity "Preparazione pacchetto IUSENTRA" -Completed
}

Write-Host "Pacchetto pronto: $Destinazione"
