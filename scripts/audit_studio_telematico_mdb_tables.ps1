param(
    [string]$Mdb = "D:\QuickOrganizer\QuickOrganizer.mdb",
    [string]$Output = "artifacts\deposito-telematico\audit-tabelle-mdb-studio-telematico-2026-08-13.json"
)

$ErrorActionPreference = "Stop"

if ([Environment]::Is64BitProcess) {
    $powershell32 = Join-Path $env:WINDIR "SysWOW64\WindowsPowerShell\v1.0\powershell.exe"
    if (-not (Test-Path -LiteralPath $powershell32)) {
        throw "PowerShell a 32 bit non disponibile per il provider Jet OLEDB."
    }
    & $powershell32 -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -Mdb $Mdb -Output $Output
    exit $LASTEXITCODE
}

$mdbPath = [IO.Path]::GetFullPath($Mdb)
$outputPath = [IO.Path]::GetFullPath($Output)
if (-not (Test-Path -LiteralPath $mdbPath)) {
    throw "Database Studio Telematico non trovato: $mdbPath"
}

$connectionString = "Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$mdbPath;Jet OLEDB:Database Password=;Mode=Read;"
$connection = New-Object System.Data.OleDb.OleDbConnection($connectionString)
$tables = @()

try {
    $connection.Open()
    $schema = $connection.GetSchema("Tables")
    foreach ($row in ($schema | Where-Object { $_.TABLE_TYPE -eq "TABLE" } | Sort-Object TABLE_NAME)) {
        $tableName = [string]$row.TABLE_NAME
        $restrictions = New-Object string[] 4
        $restrictions[2] = $tableName
        $columnSchema = $connection.GetSchema("Columns", $restrictions)
        $columns = @()
        foreach ($column in ($columnSchema | Sort-Object ORDINAL_POSITION)) {
            $columns += [ordered]@{
                name = [string]$column.COLUMN_NAME
                ordinal = [int]$column.ORDINAL_POSITION
                data_type = [int]$column.DATA_TYPE
                type_name = [string]$column.TYPE_NAME
                max_length = if ($column.CHARACTER_MAXIMUM_LENGTH -is [DBNull]) { $null } else { [int]$column.CHARACTER_MAXIMUM_LENGTH }
                nullable = if ($column.IS_NULLABLE -is [DBNull]) { $null } else { [bool]$column.IS_NULLABLE }
            }
        }
        $escapedTableName = $tableName.Replace("]", "]]" )
        $command = $connection.CreateCommand()
        $command.CommandText = "SELECT COUNT(*) FROM [$escapedTableName]"
        $rowCount = [int64]$command.ExecuteScalar()
        $command.Dispose()
        $tables += [ordered]@{
            name = $tableName
            row_count = $rowCount
            columns = $columns
        }
    }
}
finally {
    if ($connection.State -eq [System.Data.ConnectionState]::Open) {
        $connection.Close()
    }
    $connection.Dispose()
}

$relevantNames = @("PRATICHE", "NOMI", "TAVOLA", "EMAILS", "Titoli", "PrecisazioneCredito")
$result = [ordered]@{
    schema_version = "1.0"
    generated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
    source = [ordered]@{
        path = $mdbPath
        sha256 = (Get-FileHash -LiteralPath $mdbPath -Algorithm SHA256).Hash.ToLowerInvariant()
        size_bytes = (Get-Item -LiteralPath $mdbPath).Length
    }
    privacy = "Nessun contenuto delle righe e' esportato: soltanto schema e conteggi."
    table_count = $tables.Count
    deposit_relevant_tables = @($tables | Where-Object { $relevantNames -contains $_.name } | ForEach-Object { $_.name })
    tables = $tables
}

$outputDirectory = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
$json = $result | ConvertTo-Json -Depth 12
[IO.File]::WriteAllText($outputPath, $json + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
$summary = [pscustomobject]@{
    schema_version = $result.schema_version
    generated_at = $result.generated_at
    table_count = $result.table_count
    deposit_relevant_tables = $result.deposit_relevant_tables
}
Write-Output ($summary | ConvertTo-Json -Depth 4)
