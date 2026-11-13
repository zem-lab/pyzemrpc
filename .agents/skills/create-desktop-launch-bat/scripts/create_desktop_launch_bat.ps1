[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [string]$DestinationPath,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = (& git -C $PSScriptRoot rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($RepositoryRoot)) {
        throw 'Unable to resolve the repository root. Pass -RepositoryRoot explicitly.'
    }
}

$RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path.TrimEnd('\')
$sourcePath = Join-Path $RepositoryRoot 'ZEMrpc.bat'
if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
    throw "Launcher source not found: $sourcePath"
}

if ([string]::IsNullOrWhiteSpace($DestinationPath)) {
    $desktopPath = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
    if ([string]::IsNullOrWhiteSpace($desktopPath)) {
        throw 'Unable to resolve the Windows desktop directory.'
    }
    $DestinationPath = Join-Path $desktopPath 'ZEMrpc.bat'
}

$destinationDirectory = Split-Path -Parent $DestinationPath
if (-not (Test-Path -LiteralPath $destinationDirectory -PathType Container)) {
    throw "Destination directory not found: $destinationDirectory"
}

$template = Get-Content -Raw -LiteralPath $sourcePath
$rootResolverPattern = '(?m)^for %%I in \("%~dp0\."\) do set "APP_DIR=%%~fI"(?=\r?$)'
$matches = [regex]::Matches($template, $rootResolverPattern)
if ($matches.Count -ne 1) {
    throw 'ZEMrpc.bat does not contain the expected repository-root resolver.'
}

$batchRepositoryRoot = $RepositoryRoot.Replace('%', '%%')
$launcher = [regex]::Replace(
    $template,
    $rootResolverPattern,
    [System.Text.RegularExpressions.MatchEvaluator]{
        param($match)
        return 'set "APP_DIR=' + $batchRepositoryRoot + '"'
    }
)

if (Test-Path -LiteralPath $DestinationPath -PathType Leaf) {
    $current = Get-Content -Raw -LiteralPath $DestinationPath
    if ($current -eq $launcher) {
        Write-Output "Desktop launcher is already current: $DestinationPath"
        exit 0
    }
    if (-not $Force) {
        throw "Destination already exists and differs: $DestinationPath. Inspect it, then rerun with -Force to replace it."
    }
}

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($DestinationPath, $launcher, $utf8NoBom)
Write-Output "Created desktop launcher: $DestinationPath"
