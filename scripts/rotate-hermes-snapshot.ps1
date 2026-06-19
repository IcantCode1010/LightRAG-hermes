[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ArchiveLabel = ""
)

$ErrorActionPreference = "Stop"

function Resolve-OrCreateDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Assert-UnderDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $resolvedParent = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\') + '\'
    if (-not $resolvedPath.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside expected directory: $resolvedPath"
    }
}

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$dataRoot = Resolve-OrCreateDirectory (Join-Path $repoRoot "data")

# Rotates repo-local data\hermes_snapshot into data\hermes_snapshot_archive.
$snapshotPath = Join-Path $dataRoot "hermes_snapshot"
$archiveRoot = Join-Path $dataRoot "hermes_snapshot_archive"

Assert-UnderDirectory -Path $snapshotPath -Parent $dataRoot
Assert-UnderDirectory -Path $archiveRoot -Parent $dataRoot

if ([string]::IsNullOrWhiteSpace($ArchiveLabel)) {
    $ArchiveLabel = Get-Date -Format "yyyyMMdd_HHmmss"
}

$safeLabel = $ArchiveLabel -replace "[^A-Za-z0-9_.-]", "_"
$archivePath = Join-Path $archiveRoot "hermes_snapshot_$safeLabel"
$counter = 1
while (Test-Path -LiteralPath $archivePath) {
    $archivePath = Join-Path $archiveRoot "hermes_snapshot_${safeLabel}_$counter"
    $counter++
}

Assert-UnderDirectory -Path $archivePath -Parent $archiveRoot

if (Test-Path -LiteralPath $snapshotPath) {
    if ($PSCmdlet.ShouldProcess($snapshotPath, "archive to $archivePath")) {
        New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
        Move-Item -LiteralPath $snapshotPath -Destination $archivePath
        Write-Host "Archived Hermes snapshot storage to $archivePath"
    }
}
else {
    Write-Host "No existing Hermes snapshot storage found at $snapshotPath"
}

if ($PSCmdlet.ShouldProcess($snapshotPath, "create fresh snapshot directories")) {
    New-Item -ItemType Directory -Path (Join-Path $snapshotPath "rag_storage") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $snapshotPath "inputs") -Force | Out-Null
    Write-Host "Created fresh Hermes snapshot directories at $snapshotPath"
}
