param(
    [string]$CartellaStudioTelematico = "C:\QuickOrganizer",
    [string]$Destinazione = "",
    [string]$AutoUploadBaseUrl = "",
    [string]$AutoUploadToken = "",
    [string]$AutoSessionId = "",
    [int]$AutoChunkSizeBytes = 67108864
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
        if ($AutoUploadBaseUrl) { $args += @("-AutoUploadBaseUrl", $AutoUploadBaseUrl) }
        if ($AutoUploadToken) { $args += @("-AutoUploadToken", $AutoUploadToken) }
        if ($AutoSessionId) { $args += @("-AutoSessionId", $AutoSessionId) }
        if ($AutoChunkSizeBytes) { $args += @("-AutoChunkSizeBytes", $AutoChunkSizeBytes) }
        & $ps32 @args
        exit $LASTEXITCODE
    }
}

Restart-InPowerShell32

function Test-IusentraAutoUpload {
    return ([bool]$AutoUploadBaseUrl -and [bool]$AutoUploadToken)
}

function Get-IusentraAutoUrl {
    param([string]$Path)
    $base = $AutoUploadBaseUrl.TrimEnd("/")
    return $base + $Path
}

function Get-IusentraAutoHeaders {
    return @{ "X-IUSENTRA-Auto-Import-Token" = $AutoUploadToken }
}

function Send-IusentraStatus {
    param(
        [string]$Status,
        [int]$Progress,
        [string]$Detail,
        [string]$Errore = ""
    )
    if (-not (Test-IusentraAutoUpload)) { return }
    $body = [ordered]@{
        status = $Status
        progress = [Math]::Max(0, [Math]::Min(100, $Progress))
        detail = $Detail
    }
    if ($Errore) { $body.errore = $Errore }
    try {
        Invoke-RestMethod `
            -Method Post `
            -Uri (Get-IusentraAutoUrl "/stato") `
            -Headers (Get-IusentraAutoHeaders) `
            -ContentType "application/json; charset=utf-8" `
            -Body ($body | ConvertTo-Json -Depth 5) `
            -UseBasicParsing | Out-Null
    } catch {
        Write-Warning "Aggiornamento stato IUSENTRA non riuscito: $($_.Exception.Message)"
    }
}

function Invoke-IusentraAutoUpload {
    param([string]$PackagePath)
    if (-not (Test-IusentraAutoUpload)) { return }
    if (-not (Test-Path -LiteralPath $PackagePath)) {
        throw "Pacchetto da caricare non trovato: $PackagePath"
    }

    $fileInfo = Get-Item -LiteralPath $PackagePath
    Send-IusentraStatus -Status "uploading" -Progress 55 -Detail "Caricamento pacchetto verso IUSENTRA in corso."
    $startBody = [ordered]@{
        filename = $fileInfo.Name
        totalSize = [int64]$fileInfo.Length
    }
    $upload = Invoke-RestMethod `
        -Method Post `
        -Uri (Get-IusentraAutoUrl "/upload-session") `
        -Headers (Get-IusentraAutoHeaders) `
        -ContentType "application/json; charset=utf-8" `
        -Body ($startBody | ConvertTo-Json -Depth 5) `
        -UseBasicParsing

    $uploadId = [string]$upload.uploadId
    if (-not $uploadId) {
        throw "Sessione di caricamento IUSENTRA non avviata."
    }
    $chunkSize = [int64]$AutoChunkSizeBytes
    if ($upload.chunkSizeBytes) { $chunkSize = [int64]$upload.chunkSizeBytes }
    if ($chunkSize -lt 1048576) { $chunkSize = 1048576 }
    $totalChunks = [Math]::Max(1, [int][Math]::Ceiling($fileInfo.Length / [double]$chunkSize))
    $buffer = New-Object byte[] ([Math]::Min(1048576, [int]$chunkSize))
    $input = [System.IO.File]::Open($fileInfo.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    $chunkPath = ""
    try {
        for ($index = 0; $index -lt $totalChunks; $index++) {
            $chunkPath = Join-Path $env:TEMP ("iusentra-import-" + [Guid]::NewGuid().ToString("N") + ".part")
            $output = [System.IO.File]::Open($chunkPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
            try {
                $remaining = $chunkSize
                while ($remaining -gt 0) {
                    $toRead = [Math]::Min($buffer.Length, $remaining)
                    $read = $input.Read($buffer, 0, [int]$toRead)
                    if ($read -le 0) { break }
                    $output.Write($buffer, 0, $read)
                    $remaining -= $read
                }
            } finally {
                $output.Dispose()
            }

            $percent = [Math]::Min(94, 55 + [Math]::Floor((($index + 1) / $totalChunks) * 38))
            Write-Progress -Activity "Caricamento pacchetto IUSENTRA" -Status "Blocco $($index + 1)/$totalChunks" -PercentComplete $percent
            $chunkUrl = Get-IusentraAutoUrl ("/upload-session/" + $uploadId + "/chunk?index=" + $index + "&totalChunks=" + $totalChunks)
            Invoke-WebRequest `
                -Method Post `
                -Uri $chunkUrl `
                -Headers (Get-IusentraAutoHeaders) `
                -InFile $chunkPath `
                -ContentType "application/octet-stream" `
                -UseBasicParsing | Out-Null
            Remove-Item -LiteralPath $chunkPath -Force
            $chunkPath = ""
            Send-IusentraStatus -Status "uploading" -Progress $percent -Detail "Caricati $($index + 1) blocchi su $totalChunks."
        }
    } finally {
        $input.Dispose()
        if ($chunkPath -and (Test-Path -LiteralPath $chunkPath)) {
            Remove-Item -LiteralPath $chunkPath -Force
        }
        Write-Progress -Activity "Caricamento pacchetto IUSENTRA" -Completed
    }

    Send-IusentraStatus -Status "checking" -Progress 96 -Detail "Controllo del pacchetto caricato in corso."
    $completeBody = [ordered]@{ totalChunks = $totalChunks }
    Invoke-RestMethod `
        -Method Post `
        -Uri (Get-IusentraAutoUrl ("/upload-session/" + $uploadId + "/completa")) `
        -Headers (Get-IusentraAutoHeaders) `
        -ContentType "application/json; charset=utf-8" `
        -Body ($completeBody | ConvertTo-Json -Depth 5) `
        -UseBasicParsing | Out-Null
    Send-IusentraStatus -Status "ready" -Progress 100 -Detail "Pacchetto caricato e controllato in IUSENTRA."
}

trap {
    $message = $_.Exception.Message
    if (-not $message) { $message = [string]$_ }
    Send-IusentraStatus -Status "error" -Progress 100 -Detail $message -Errore $message
    throw
}

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

Send-IusentraStatus -Status "preparing" -Progress 5 -Detail "Ricerca della cartella Studio Telematico in corso."
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
Send-IusentraStatus -Status "preparing" -Progress 10 -Detail "Cartella Studio Telematico trovata. Lettura archivio dati in corso."

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
Send-IusentraStatus -Status "preparing" -Progress 28 -Detail "Archivio dati letto. Verifica collegamenti pratiche, clienti e parti."

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
Send-IusentraStatus -Status "packing" -Progress 35 -Detail "Creazione pacchetto con quickorganizer-export.json, ATTI ed EMAILS."

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
    Send-IusentraStatus -Status "packing" -Progress 38 -Detail "Scrittura archivio dati nel pacchetto."
    Add-TextEntryToZip -Archive $archive -EntryName "quickorganizer-export.json" -Content $json
    Send-IusentraStatus -Status "packing" -Progress 42 -Detail "Aggiunta documenti dalla cartella ATTI."
    Add-FolderToZip -Archive $archive -SourceFolder $atti -EntryRoot "ATTI"
    Send-IusentraStatus -Status "packing" -Progress 50 -Detail "Aggiunta email dalla cartella EMAILS."
    Add-FolderToZip -Archive $archive -SourceFolder $emails -EntryRoot "EMAILS"
} finally {
    $archive.Dispose()
    $zipStream.Dispose()
    Write-Progress -Activity "Preparazione pacchetto IUSENTRA" -Completed
}

Write-Host "Pacchetto pronto: $Destinazione"
Send-IusentraStatus -Status "packing" -Progress 54 -Detail "Pacchetto creato. Avvio caricamento automatico in IUSENTRA."
Invoke-IusentraAutoUpload -PackagePath $Destinazione
