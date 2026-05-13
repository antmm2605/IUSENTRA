param(
    [string]$EnvFile = ".env",
    [string]$DataDir = "data",
    [string]$Bucket = "iusentra-audit-worm",
    [string]$Kid = "iusentra-local-audit-jws"
)

$ErrorActionPreference = "Stop"

function New-HexSecret([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    } finally {
        $rng.Dispose()
    }
    return -join ($buffer | ForEach-Object { $_.ToString("x2") })
}

function Set-EnvValue([string]$Key, [string]$Value) {
    $path = Resolve-Path -LiteralPath $EnvFile -ErrorAction SilentlyContinue
    if (-not $path) {
        New-Item -ItemType File -Path $EnvFile -Force | Out-Null
    }
    $lines = @(Get-Content -LiteralPath $EnvFile -ErrorAction SilentlyContinue)
    $updated = $false
    $escaped = [regex]::Escape($Key)
    $next = foreach ($line in $lines) {
        if ($line -match "^$escaped=") {
            "$Key=$Value"
            $updated = $true
        } else {
            $line
        }
    }
    if (-not $updated) {
        $next += "$Key=$Value"
    }
    Set-Content -LiteralPath $EnvFile -Value $next -Encoding UTF8
}

function Get-EnvValue([string]$Key) {
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        return ""
    }
    $escaped = [regex]::Escape($Key)
    $line = Get-Content -LiteralPath $EnvFile | Where-Object { $_ -match "^$escaped=" } | Select-Object -First 1
    if (-not $line) {
        return ""
    }
    return ($line -split "=", 2)[1].Trim()
}

function Add-ComposeProfile([string]$Profile) {
    $current = Get-EnvValue "COMPOSE_PROFILES"
    $items = @()
    if ($current) {
        $items = $current -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    }
    if ($items -notcontains $Profile) {
        $items += $Profile
    }
    Set-EnvValue "COMPOSE_PROFILES" ($items -join ",")
}

$keyDir = Join-Path $DataDir "audit\keys"
New-Item -ItemType Directory -Path $keyDir -Force | Out-Null
$privateKey = Join-Path $keyDir "audit_jws_private.pem"
$publicKey = Join-Path $keyDir "audit_jws_public.pem"

$python = @'
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

private_path = Path(os.environ["IUSENTRA_AUDIT_PRIVATE_KEY"])
public_path = Path(os.environ["IUSENTRA_AUDIT_PUBLIC_KEY"])
private_path.parent.mkdir(parents=True, exist_ok=True)

if not private_path.exists():
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
elif not public_path.exists():
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

public_key = serialization.load_pem_public_key(public_path.read_bytes())
public_der = public_key.public_bytes(
    serialization.Encoding.DER,
    serialization.PublicFormat.SubjectPublicKeyInfo,
)
print(json.dumps({"fingerprint": hashlib.sha256(public_der).hexdigest()}))
'@

$resolvedPrivate = Resolve-Path -LiteralPath $privateKey -ErrorAction SilentlyContinue
$resolvedPublic = Resolve-Path -LiteralPath $publicKey -ErrorAction SilentlyContinue
$env:IUSENTRA_AUDIT_PRIVATE_KEY = if ($resolvedPrivate) { $resolvedPrivate.Path } else { $privateKey }
$env:IUSENTRA_AUDIT_PUBLIC_KEY = if ($resolvedPublic) { $resolvedPublic.Path } else { $publicKey }
$keyInfo = $python | python - | ConvertFrom-Json

$accessKey = Get-EnvValue "AUDIT_WORM_ACCESS_KEY"
if (-not $accessKey) {
    $accessKey = "iusentraaudit" + (New-HexSecret 8)
}
$secretKey = Get-EnvValue "AUDIT_WORM_SECRET_KEY"
if (-not $secretKey) {
    $secretKey = New-HexSecret 32
}
$postgresPassword = Get-EnvValue "AUDIT_POSTGRES_PASSWORD"
if (-not $postgresPassword) {
    $postgresPassword = New-HexSecret 32
}

Add-ComposeProfile "audit-worm"
Set-EnvValue "AUDIT_ENABLED" "true"
Set-EnvValue "AUDIT_ENV" "development"
Set-EnvValue "AUDIT_REQUIRE_WORM" "true"
Set-EnvValue "AUDIT_REQUIRE_SIGNATURE" "true"
Set-EnvValue "AUDIT_REQUIRE_TSA_FOR_SNAPSHOT" "false"
Set-EnvValue "AUDIT_RETENTION_YEARS" "10"
Set-EnvValue "AUDIT_CANONICALIZATION" "RFC8785-JCS"
Set-EnvValue "AUDIT_HASH_ALG" "SHA-256"
Set-EnvValue "AUDIT_POSTGRES_DB" "iusentra_audit"
Set-EnvValue "AUDIT_POSTGRES_USER" "iusentra_audit"
Set-EnvValue "AUDIT_POSTGRES_PASSWORD" $postgresPassword
Set-EnvValue "AUDIT_DATABASE_URL" "postgresql://iusentra_audit:$postgresPassword@audit-postgres:5432/iusentra_audit"
Set-EnvValue "AUDIT_WORM_ENDPOINT_URL" "http://audit-worm:9000"
Set-EnvValue "AUDIT_WORM_REGION" "eu-central-1"
Set-EnvValue "AUDIT_WORM_BUCKET" $Bucket
Set-EnvValue "AUDIT_WORM_ACCESS_KEY" $accessKey
Set-EnvValue "AUDIT_WORM_SECRET_KEY" $secretKey
Set-EnvValue "AUDIT_WORM_RETENTION_YEARS" "10"
Set-EnvValue "AUDIT_WORM_MODE" "COMPLIANCE"
Set-EnvValue "AUDIT_WORM_REQUIRE_OBJECT_LOCK" "true"
Set-EnvValue "AUDIT_SIGNING_MODE" "JWS"
Set-EnvValue "AUDIT_SIGNING_KID" $Kid
Set-EnvValue "AUDIT_SIGNING_ALG" "RS256"
Set-EnvValue "AUDIT_SIGNING_KEY_SOURCE" "KEY_VAULT_FILE"
Set-EnvValue "AUDIT_SIGNING_KEY_SEALED" "true"
Set-EnvValue "AUDIT_SIGNING_PRIVATE_KEY_FILE" "/data/audit/keys/audit_jws_private.pem"
Set-EnvValue "AUDIT_SIGNING_PUBLIC_KEY_FILE" "/data/audit/keys/audit_jws_public.pem"
Set-EnvValue "AUDIT_SIGNING_CERT_FINGERPRINT" $keyInfo.fingerprint

Write-Host "Audit WORM locale configurato in $EnvFile."
Write-Host "Chiave JWS fuori repository: $privateKey"
Write-Host "Avvio: docker compose --profile audit-worm up -d --build"
