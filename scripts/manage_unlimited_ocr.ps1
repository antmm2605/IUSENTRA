param(
    [ValidateSet("doctor", "start", "health", "logs", "stop")]
    [string]$Action = "doctor",
    [int]$TimeoutSeconds = 1800,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ComposeFile = Join-Path $RepoRoot "deploy\unlimited-ocr\docker-compose.unlimited-ocr.yml"
$Endpoint = if ($env:IUSENTRA_UNLIMITED_OCR_ENDPOINT) { $env:IUSENTRA_UNLIMITED_OCR_ENDPOINT } else { "http://127.0.0.1:10000" }

function Test-Exe([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    return [bool]$cmd
}

function Get-DockerRuntimes {
    try {
        return docker info --format '{{json .Runtimes}}' 2>$null
    } catch {
        return ""
    }
}

function Get-VideoControllers {
    try {
        return @(Get-CimInstance Win32_VideoController | ForEach-Object {
            [ordered]@{
                name = $_.Name
                driver_version = $_.DriverVersion
                status = $_.Status
            }
        })
    } catch {
        return @()
    }
}

function Test-NvidiaSmi {
    if (-not (Test-Exe "nvidia-smi")) {
        return [ordered]@{ available = $false; output = "nvidia-smi non trovato nel PATH." }
    }
    try {
        $out = nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1
        return [ordered]@{ available = $LASTEXITCODE -eq 0; output = ($out -join "`n") }
    } catch {
        return [ordered]@{ available = $false; output = $_.Exception.Message }
    }
}

function Get-DoctorReport {
    $docker = Test-Exe "docker"
    $compose = $false
    if ($docker) {
        try {
            docker compose version *> $null
            $compose = $LASTEXITCODE -eq 0
        } catch {
            $compose = $false
        }
    }
    $runtimes = Get-DockerRuntimes
    $video = Get-VideoControllers
    $nvidia = Test-NvidiaSmi
    $hasNvidiaVideo = @($video | Where-Object { [string]($_.name) -match "NVIDIA" }).Count -gt 0
    $hasNvidiaRuntime = [string]$runtimes -match '"nvidia"'
    $python312 = $false
    try {
        py -3.12 --version *> $null
        $python312 = $LASTEXITCODE -eq 0
    } catch {
        $python312 = $false
    }
    $ready = $docker -and $compose -and ($nvidia.available -or ($hasNvidiaVideo -and $hasNvidiaRuntime))
    return [ordered]@{
        ok = $ready
        docker = $docker
        docker_compose = $compose
        docker_nvidia_runtime = $hasNvidiaRuntime
        nvidia_smi = $nvidia
        video_controllers = $video
        python_312 = $python312
        compose_file = $ComposeFile
        endpoint = $Endpoint
        resolution = if ($ready) {
            "Host pronto per avviare Unlimited-OCR self-hosted."
        } else {
            "Host locale non pronto per Unlimited-OCR GPU: usare un host con NVIDIA/CUDA oppure endpoint privato già avviato; IUSENTRA resta cablato e fail-closed."
        }
    }
}

function Invoke-EndpointHealth([switch]$Smoke) {
    $env:IUSENTRA_UNLIMITED_OCR_ENABLED = "1"
    $env:IUSENTRA_UNLIMITED_OCR_ENDPOINT = $Endpoint
    $args = @("scripts\check_unlimited_ocr_endpoint.py", "--endpoint", $Endpoint, "--json")
    if ($Smoke) {
        $args += "--smoke"
    }
    & python @args
    return $LASTEXITCODE
}

function Wait-Endpoint {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        & python scripts\check_unlimited_ocr_endpoint.py --endpoint $Endpoint --json | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        Start-Sleep -Seconds 10
    }
    return $false
}

Set-Location $RepoRoot

if ($Action -eq "doctor") {
    $report = Get-DoctorReport
    $report | ConvertTo-Json -Depth 8
    exit 0
}

if ($Action -eq "health") {
    exit (Invoke-EndpointHealth -Smoke)
}

if ($Action -eq "logs") {
    docker compose -f $ComposeFile --profile unlimited-ocr logs --tail=200 unlimited-ocr
    exit $LASTEXITCODE
}

if ($Action -eq "stop") {
    docker compose -f $ComposeFile --profile unlimited-ocr down
    exit $LASTEXITCODE
}

if ($Action -eq "start") {
    $report = Get-DoctorReport
    if (-not $report.ok -and -not $Force) {
        $report | ConvertTo-Json -Depth 8
        exit 2
    }
    docker compose -f $ComposeFile --profile unlimited-ocr up -d
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    if (-not (Wait-Endpoint)) {
        docker compose -f $ComposeFile --profile unlimited-ocr logs --tail=120 unlimited-ocr
        exit 2
    }
    exit (Invoke-EndpointHealth -Smoke)
}
