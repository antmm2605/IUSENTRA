param(
    [string]$CartellaStudioTelematico = "C:\QuickOrganizer",
    [string]$Destinazione = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Restart-InPowerShell32 {
    $windir = $env:WINDIR
    if (-not $windir) { $windir = "C:\Windows" }
    $ps32 = Join-Path $windir "SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
    if ((Test-Path $ps32) -and $env:PROCESSOR_ARCHITEW6432) {
        $args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath, "-CartellaStudioTelematico", $CartellaStudioTelematico)
        if ($Destinazione) { $args += @("-Destinazione", $Destinazione) }
        & $ps32 @args
        exit $LASTEXITCODE
    }
}

Restart-InPowerShell32

$root = [System.IO.Path]::GetFullPath($CartellaStudioTelematico)
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
            $payload.tables[$table] = @()
        }
    }
} finally {
    $conn.Close()
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("iusentra-studio-telematico-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $jsonPath = Join-Path $tmp "quickorganizer-export.json"
    $payload | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonPath -Encoding UTF8
    Copy-Item -Path $atti -Destination (Join-Path $tmp "ATTI") -Recurse -Force
    Copy-Item -Path $emails -Destination (Join-Path $tmp "EMAILS") -Recurse -Force
    if (Test-Path $Destinazione) { Remove-Item -LiteralPath $Destinazione -Force }
    Compress-Archive -Path (Join-Path $tmp "*") -DestinationPath $Destinazione -CompressionLevel Optimal
    Write-Host "Pacchetto pronto: $Destinazione"
} finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
