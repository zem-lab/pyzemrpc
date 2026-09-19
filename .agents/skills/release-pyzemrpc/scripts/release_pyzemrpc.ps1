[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [switch]$ConfirmedWorktree,
    [switch]$ReuseArtifact,
    [switch]$RunHardwareTests,
    [switch]$Publish,

    [string]$DevpiIndex = "http://dc000.local:7104/zeptools/devpi",
    [string]$PyPIRepository = "pypi"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Get-AbsoluteUrl {
    param([string]$BaseUrl, [string]$Href)

    $decoded = [System.Net.WebUtility]::HtmlDecode($Href)
    if ([uri]::IsWellFormedUriString($decoded, [System.UriKind]::Absolute)) {
        return $decoded
    }
    return ([uri]::new([uri]$BaseUrl, $decoded)).AbsoluteUri
}

function Invoke-ReleaseWebRequest {
    param([string]$Url, [int]$TimeoutSec = 20)

    try {
        return Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
    }
    catch {
        $response = $_.Exception.Response
        if ($null -ne $response -and [int]$response.StatusCode -eq 404) {
            return $null
        }
        throw
    }
}

function Get-DevpiDirectWheelUrl {
    param(
        [string]$SimpleUrl,
        [string]$IndexUrl,
        [string]$Filename
    )

    $response = Invoke-ReleaseWebRequest -Url $SimpleUrl
    if ($null -eq $response) {
        return $null
    }
    if ([int]$response.StatusCode -ne 200) {
        throw "devpi simple index returned HTTP $([int]$response.StatusCode): $SimpleUrl"
    }

    $stagePath = ([uri]$IndexUrl).AbsolutePath.TrimEnd("/") + "/+f/"
    foreach ($link in @($response.Links)) {
        if ($null -eq $link.href -or $link.href -notmatch [regex]::Escape($Filename)) {
            continue
        }
        $absolute = Get-AbsoluteUrl -BaseUrl $SimpleUrl -Href $link.href
        if (([uri]$absolute).AbsolutePath.StartsWith($stagePath, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $absolute
        }
    }
    return $null
}

function Get-RemoteSha256 {
    param([string]$Url)

    $fragment = ([uri]$Url).Fragment
    if ($fragment -match "^#sha256=([0-9a-fA-F]{64})$") {
        return $Matches[1].ToLowerInvariant()
    }

    $client = New-Object System.Net.WebClient
    try {
        $bytes = $client.DownloadData($Url)
    }
    finally {
        $client.Dispose()
    }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Get-PyPIWheel {
    param([string]$PackageVersion, [string]$Filename)

    $url = "https://pypi.org/pypi/pyzemrpc/$PackageVersion/json"
    $response = Invoke-ReleaseWebRequest -Url $url
    if ($null -eq $response) {
        return $null
    }
    if ([int]$response.StatusCode -ne 200) {
        throw "PyPI version endpoint returned HTTP $([int]$response.StatusCode): $url"
    }

    $data = $response.Content | ConvertFrom-Json
    return $data.urls | Where-Object { $_.filename -eq $Filename } | Select-Object -First 1
}

function Wait-ForPyPIWheel {
    param([string]$PackageVersion, [string]$Filename)

    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        $file = Get-PyPIWheel -PackageVersion $PackageVersion -Filename $Filename
        if ($null -ne $file) {
            return $file
        }
        Start-Sleep -Seconds 2
    }
    throw "PyPI did not expose $Filename within the verification window"
}

function Wait-ForDevpiWheel {
    param([string]$SimpleUrl, [string]$IndexUrl, [string]$Filename)

    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        $url = Get-DevpiDirectWheelUrl -SimpleUrl $SimpleUrl -IndexUrl $IndexUrl -Filename $Filename
        if ($null -ne $url) {
            return $url
        }
        Start-Sleep -Seconds 2
    }
    throw "devpi did not expose a direct-stage link for $Filename within the verification window"
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..\..\..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$invoke = Join-Path $repoRoot ".venv\Scripts\invoke.exe"
$devpi = Join-Path $repoRoot ".venv\Scripts\devpi.exe"
$versionFile = Join-Path $repoRoot "zemrpc\__version__.py"
$distDir = Join-Path $repoRoot "dist"
$helper = Join-Path $PSScriptRoot "release_helper.py"
$filename = "pyzemrpc-$Version-py3-none-any.whl"
$wheel = Join-Path $distDir $filename
$simpleUrl = $DevpiIndex.TrimEnd("/") + "/+simple/pyzemrpc/"

foreach ($required in @($python, $invoke, $helper)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required project tool is missing: $required"
    }
}

Push-Location $repoRoot
try {
    Invoke-Native $python -c "from packaging.version import Version; import sys; value=Version(sys.argv[1]); print('Normalized version:', value); assert str(value) == sys.argv[1], 'version must already be normalized'" $Version
    Invoke-Native $python -c "import build, packaging, twine; from packaging.version import Version; assert Version(packaging.__version__) >= Version('24.2'), packaging.__version__"

    $versionText = Get-Content -LiteralPath $versionFile -Raw
    if ($versionText -notmatch '(?m)^__version__\s*=\s*["'']([^"'']+)["'']') {
        throw "Unable to read __version__ from $versionFile"
    }
    if ($Matches[1] -ne $Version) {
        throw "zemrpc/__version__.py contains '$($Matches[1])', expected '$Version'. Update it with apply_patch first."
    }

    $status = @(git status --short)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect the Git worktree"
    }
    if ($status.Count -gt 0) {
        Write-Host "Worktree changes included in this release:"
        $status | ForEach-Object { Write-Host "  $_" }
        if (-not $ConfirmedWorktree) {
            throw "The worktree is dirty. Inspect the changes and rerun with -ConfirmedWorktree only when they belong in this release."
        }
    }

    if (-not $ReuseArtifact) {
        Invoke-Native $invoke git_info ui2py
        Invoke-Native $invoke clean_build
        if (-not (Test-Path -LiteralPath $distDir)) {
            New-Item -ItemType Directory -Path $distDir | Out-Null
        }
        Invoke-Native $python -m build --wheel --outdir $distDir
    }

    if (-not (Test-Path -LiteralPath $wheel -PathType Leaf)) {
        throw "Expected wheel not found: $wheel"
    }

    Invoke-Native $python -m twine check $wheel
    $head = (git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to resolve the current Git commit"
    }

    Invoke-Native $python $helper inspect-wheel $wheel $Version $head

    $localHash = (Get-FileHash -LiteralPath $wheel -Algorithm SHA256).Hash.ToLowerInvariant()
    $localSize = (Get-Item -LiteralPath $wheel).Length
    Write-Host "Artifact: $wheel"
    Write-Host "Size: $localSize"
    Write-Host "SHA256: $localHash"

    Invoke-Native $python -m pip install --no-deps --force-reinstall $wheel
    Invoke-Native $python -m pytest tests --ignore=tests/test_zem_api.py -q
    if ($RunHardwareTests) {
        Invoke-Native $python -m pytest tests/test_zem_api.py -q
    }

    if (-not $Publish) {
        Write-Host "Validation complete. No upload was requested; rerun with -ReuseArtifact -Publish to publish these exact bytes."
        exit 0
    }

    if (-not (Test-Path -LiteralPath $devpi -PathType Leaf)) {
        throw "devpi-client is required for publishing: $devpi"
    }

    $pypiFile = Get-PyPIWheel -PackageVersion $Version -Filename $filename
    if ($null -ne $pypiFile -and $pypiFile.digests.sha256.ToLowerInvariant() -ne $localHash) {
        throw "PyPI already contains $filename with a different SHA256. PyPI releases are immutable; do not rebuild or overwrite it."
    }

    $devpiUrl = Get-DevpiDirectWheelUrl -SimpleUrl $simpleUrl -IndexUrl $DevpiIndex -Filename $filename
    if ($null -ne $devpiUrl) {
        $devpiHash = Get-RemoteSha256 -Url $devpiUrl
        if ($devpiHash -ne $localHash) {
            throw "devpi already contains $filename with a different SHA256"
        }
    }

    $needsDevpi = $null -eq $devpiUrl
    $needsPyPI = $null -eq $pypiFile

    if ($needsDevpi) {
        $useOutput = (& $devpi use 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to inspect the current devpi session"
        }
        Write-Host $useOutput.TrimEnd()
        if ($useOutput -notmatch "logged in as") {
            throw "devpi is not logged in. Run '.\.venv\Scripts\devpi.exe login zeptools' and rerun with -ReuseArtifact -Publish."
        }
    }

    if ($needsPyPI) {
        $pypirc = Join-Path $env:USERPROFILE ".pypirc"
        if (-not (Test-Path -LiteralPath $pypirc -PathType Leaf)) {
            throw "PyPI credentials are unavailable: $pypirc is missing"
        }
        Invoke-Native $python $helper check-pypirc $pypirc $PyPIRepository
    }

    if ($needsDevpi) {
        Invoke-Native $devpi upload --index $DevpiIndex $wheel
    }
    else {
        Write-Host "devpi already contains the identical direct-stage wheel; skipping upload."
    }

    if ($needsPyPI) {
        Invoke-Native $python -m twine upload --non-interactive --disable-progress-bar --repository $PyPIRepository $wheel
    }
    else {
        Write-Host "PyPI already contains the identical wheel; skipping upload."
    }

    $verifiedPyPI = Wait-ForPyPIWheel -PackageVersion $Version -Filename $filename
    if ($verifiedPyPI.digests.sha256.ToLowerInvariant() -ne $localHash -or [long]$verifiedPyPI.size -ne $localSize) {
        throw "PyPI integrity verification failed for $filename"
    }

    $verifiedDevpiUrl = Wait-ForDevpiWheel -SimpleUrl $simpleUrl -IndexUrl $DevpiIndex -Filename $filename
    $verifiedDevpiHash = Get-RemoteSha256 -Url $verifiedDevpiUrl
    if ($verifiedDevpiHash -ne $localHash) {
        throw "devpi integrity verification failed for $filename"
    }

    Write-Host "Release verified on PyPI: https://pypi.org/project/pyzemrpc/$Version/"
    Write-Host "Release verified directly on devpi: $verifiedDevpiUrl"
    Write-Host "Released SHA256: $localHash"
}
finally {
    Pop-Location
}
