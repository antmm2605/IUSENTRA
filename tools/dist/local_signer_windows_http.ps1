$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Net.Http | Out-Null

$rawPayload = [Console]::In.ReadToEnd()
$payload = $rawPayload | ConvertFrom-Json
$thumbprint = [string]$payload.cert_thumbprint
if ([string]::IsNullOrWhiteSpace($thumbprint)) {
    throw "Certificato Windows non indicato."
}
$pin = [string]$payload.pin

$certificate = Get-Item -LiteralPath ("Cert:\CurrentUser\My\" + $thumbprint)
$authenticatedKey = $null
$privateKey = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($certificate)
if (-not [string]::IsNullOrWhiteSpace($pin)) {
    if (-not ($privateKey -is [System.Security.Cryptography.RSACryptoServiceProvider])) {
        if ($privateKey) { $privateKey.Dispose() }
        throw "Il certificato selezionato non espone una chiave smart card compatibile."
    }
    $cspInfo = $privateKey.CspKeyContainerInfo
    $securePin = ConvertTo-SecureString -String $pin -AsPlainText -Force
    $cspParameters = [System.Security.Cryptography.CspParameters]::new(
        [int]$cspInfo.ProviderType,
        [string]$cspInfo.ProviderName,
        [string]$cspInfo.KeyContainerName
    )
    $cspParameters.KeyNumber = [int]$cspInfo.KeyNumber
    $cspParameters.Flags = [System.Security.Cryptography.CspProviderFlags]::UseExistingKey
    $cspParameters.KeyPassword = $securePin
    $authenticatedKey = [System.Security.Cryptography.RSACryptoServiceProvider]::new($cspParameters)
    $certificate.PrivateKey = $authenticatedKey
}
if ($privateKey) { $privateKey.Dispose() }

$handler = [System.Net.Http.HttpClientHandler]::new()
$handler.ClientCertificateOptions = [System.Net.Http.ClientCertificateOption]::Manual
[void]$handler.ClientCertificates.Add($certificate)
$handler.CheckCertificateRevocationList = $true
$handler.AllowAutoRedirect = $true
$client = [System.Net.Http.HttpClient]::new($handler)
$client.Timeout = [System.Threading.Timeout]::InfiniteTimeSpan
$results = [System.Collections.Generic.List[object]]::new()
$batchError = ""

try {
    foreach ($item in @($payload.requests)) {
        $request = $null
        $response = $null
        $cancellation = $null
        try {
            $request = [System.Net.Http.HttpRequestMessage]::new(
                [System.Net.Http.HttpMethod]::Post,
                [Uri]([string]$item.url)
            )
            $contentType = [string]$item.content_type
            if ([string]::IsNullOrWhiteSpace($contentType)) {
                $contentType = "text/xml; charset=utf-8"
            }
            $request.Content = [System.Net.Http.StringContent]::new(
                [string]$item.soap_body,
                [System.Text.Encoding]::UTF8
            )
            $request.Content.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse($contentType)
            $soapAction = [string]$item.soap_action
            if (-not [string]::IsNullOrWhiteSpace($soapAction)) {
                [void]$request.Headers.TryAddWithoutValidation("SOAPAction", '"' + $soapAction.Trim('"') + '"')
            }
            foreach ($header in @($item.extra_headers)) {
                $headerText = [string]$header
                $separator = $headerText.IndexOf(":")
                if ($separator -gt 0) {
                    [void]$request.Headers.TryAddWithoutValidation(
                        $headerText.Substring(0, $separator).Trim(),
                        $headerText.Substring($separator + 1).Trim()
                    )
                }
            }

            $timeoutSeconds = [int]$item.max_time
            if ($timeoutSeconds -le 0) { $timeoutSeconds = 90 }
            $cancellation = [System.Threading.CancellationTokenSource]::new()
            $cancellation.CancelAfter($timeoutSeconds * 1000)
            $response = $client.SendAsync($request, $cancellation.Token).GetAwaiter().GetResult()
            $body = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
            $headerLines = [System.Collections.Generic.List[string]]::new()
            $headerLines.Add(("HTTP/1.1 {0} {1}" -f [int]$response.StatusCode, $response.ReasonPhrase))
            foreach ($header in $response.Headers) {
                $headerLines.Add(("{0}: {1}" -f $header.Key, ($header.Value -join ", ")))
            }
            foreach ($header in $response.Content.Headers) {
                $headerLines.Add(("{0}: {1}" -f $header.Key, ($header.Value -join ", ")))
            }
            $results.Add([pscustomobject]@{
                status_code = [int]$response.StatusCode
                headers_text = ($headerLines -join "`r`n") + "`r`n`r`n"
                body_b64 = [Convert]::ToBase64String($body)
                error = ""
            })
        }
        catch {
            $baseException = $_.Exception.GetBaseException()
            $batchError = [string]$baseException.Message
            $results.Add([pscustomobject]@{
                status_code = 0
                headers_text = ""
                body_b64 = ""
                error = $batchError
            })
        }
        finally {
            if ($cancellation) { $cancellation.Dispose() }
            if ($response) { $response.Dispose() }
            if ($request) { $request.Dispose() }
        }
        if (-not [string]::IsNullOrWhiteSpace($batchError)) {
            break
        }
    }
    while ($results.Count -lt @($payload.requests).Count) {
        $results.Add([pscustomobject]@{
            status_code = 0
            headers_text = ""
            body_b64 = ""
            error = "Batch interrotto dopo il primo errore: $batchError"
        })
    }
}
finally {
    $client.Dispose()
    $handler.Dispose()
    if ($authenticatedKey) { $authenticatedKey.Dispose() }
}

[Console]::Out.Write((ConvertTo-Json -InputObject $results -Compress -Depth 5))
