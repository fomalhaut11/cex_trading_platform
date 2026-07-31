[CmdletBinding()]
param(
    [ValidateRange(1, 32)]
    [int]$MaxWorkers = 4
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$graphifyVersion = "0.9.31"
$graphifyWheelSha256 = "b0d47f823f924e7f89acfee390b9f18dc3410917617c5f6f2731bd2642abf16f"
$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$requirementsLock = Join-Path $PSScriptRoot "requirements.lock"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Get-Sha256Text {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        $digest = $hasher.ComputeHash($bytes)
        return -join ($digest | ForEach-Object { $_.ToString("x2") })
    }
    finally {
        $hasher.Dispose()
    }
}

if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
    throw "LOCALAPPDATA is required for the isolated Graphify tool environment."
}

$allowedToolRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $env:LOCALAPPDATA "cex-quant-tools")
)
$toolRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $allowedToolRoot "graphify-$graphifyVersion")
)
if (-not $toolRoot.StartsWith(
    $allowedToolRoot,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Resolved Graphify tool path escaped the allowed tool directory: $toolRoot"
}

$venvRoot = Join-Path $toolRoot "venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$graphify = Join-Path $venvRoot "Scripts\graphify.exe"
$wheelDirectory = Join-Path $toolRoot "wheel"
$wheelPath = Join-Path $wheelDirectory "graphifyy-$graphifyVersion-py3-none-any.whl"

if (-not (Test-Path -LiteralPath $venvPython)) {
    $bootstrapPython = ""
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        $python311 = (
            & $pyLauncher.Source -3.11 -c "import sys; print(sys.executable)" |
                Out-String
        ).Trim()
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $python311)) {
            $bootstrapPython = $python311
        }
    }
    if ([string]::IsNullOrWhiteSpace($bootstrapPython)) {
        $bootstrapPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
    }
    if (-not (Test-Path -LiteralPath $bootstrapPython)) {
        $pythonCommand = Get-Command python -ErrorAction Stop
        $bootstrapPython = $pythonCommand.Source
    }
    Invoke-Checked -FilePath $bootstrapPython -Arguments @(
        "-c",
        "import sys; assert sys.version_info >= (3, 10), sys.version"
    )
    New-Item -ItemType Directory -Force -Path $toolRoot | Out-Null
    Invoke-Checked -FilePath $bootstrapPython -Arguments @("-m", "venv", $venvRoot)
}

if (-not (Test-Path -LiteralPath $wheelPath)) {
    New-Item -ItemType Directory -Force -Path $wheelDirectory | Out-Null
    Invoke-Checked -FilePath $venvPython -Arguments @(
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--no-deps",
        "--only-binary=:all:",
        "--dest",
        $wheelDirectory,
        "graphifyy==$graphifyVersion"
    )
}

$actualWheelHash = (
    Get-FileHash -Algorithm SHA256 -LiteralPath $wheelPath
).Hash.ToLowerInvariant()
if ($actualWheelHash -ne $graphifyWheelSha256) {
    throw "Graphify wheel SHA-256 mismatch. Expected $graphifyWheelSha256; got $actualWheelHash."
}

$installedVersion = ""
if (Test-Path -LiteralPath $graphify) {
    $installedVersion = (& $graphify --version | Out-String).Trim()
}
if ($installedVersion -ne "graphify $graphifyVersion") {
    Invoke-Checked -FilePath $venvPython -Arguments @(
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        $requirementsLock
    )
    Invoke-Checked -FilePath $venvPython -Arguments @(
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-deps",
        $wheelPath
    )
}

$verifiedVersion = (& $graphify --version | Out-String).Trim()
if ($verifiedVersion -ne "graphify $graphifyVersion") {
    throw "Unexpected Graphify version after bootstrap: $verifiedVersion"
}

Push-Location $repositoryRoot
try {
    Invoke-Checked -FilePath $graphify -Arguments @(
        "extract",
        ".",
        "--code-only",
        "--no-cluster",
        "--max-workers",
        $MaxWorkers.ToString()
    )
    Invoke-Checked -FilePath $graphify -Arguments @(
        "cluster-only",
        ".",
        "--no-label",
        "--no-viz"
    )

    $diagnosticText = (
        & $graphify diagnose multigraph `
            --graph "graphify-out\graph.json" `
            --json |
            Out-String
    )
    if ($LASTEXITCODE -ne 0) {
        throw "Graphify multigraph diagnostics failed with exit code $LASTEXITCODE."
    }
    $diagnostic = $diagnosticText | ConvertFrom-Json
    $diagnosticFailures = @(
        "non_object_edges",
        "missing_endpoint_edges",
        "dangling_endpoint_edges",
        "exact_duplicate_edges",
        "directed_same_endpoint_collapsed_edges"
    )
    foreach ($metric in $diagnosticFailures) {
        if ([int]$diagnostic.summary.$metric -ne 0) {
            throw "Graph integrity check failed: $metric=$($diagnostic.summary.$metric)"
        }
    }

    $graphPath = Join-Path $repositoryRoot "graphify-out\graph.json"
    $manifestPath = Join-Path $repositoryRoot "graphify-out\manifest.json"
    $graphText = Get-Content -Raw -Encoding utf8 -LiteralPath $graphPath
    if ($graphText.Contains($repositoryRoot)) {
        throw "Portable graph contains the absolute repository path."
    }
    $graph = $graphText | ConvertFrom-Json
    if ($graph.nodes.Count -eq 0 -or $graph.links.Count -eq 0) {
        throw "Graph extraction produced an empty graph."
    }

    $manifest = Get-Content -Raw -Encoding utf8 -LiteralPath $manifestPath |
        ConvertFrom-Json
    $sourceFiles = @($manifest.PSObject.Properties.Name | Sort-Object)
    $fingerprintRecords = foreach ($relativePath in $sourceFiles) {
        $absolutePath = Join-Path $repositoryRoot $relativePath
        if (Test-Path -LiteralPath $absolutePath -PathType Leaf) {
            $fileHash = (
                Get-FileHash -Algorithm SHA256 -LiteralPath $absolutePath
            ).Hash.ToLowerInvariant()
            "$relativePath`t$fileHash"
        }
    }
    $sourceFingerprint = Get-Sha256Text -Value ($fingerprintRecords -join "`n")
    $communityCount = @(
        $graph.nodes |
            Where-Object { $null -ne $_.community } |
            ForEach-Object { $_.community } |
            Sort-Object -Unique
    ).Count
    $builtAtCommit = [string]$graph.built_at_commit

    $snapshotLines = @(
        "# Graphify Code Graph Snapshot",
        "",
        "- Graphify: ``$verifiedVersion``",
        "- Mode: local AST ``--code-only``; no LLM; no semantic document extraction",
        "- Clustering: local, unlabeled, no remote visualization assets",
        "- Indexed source files: $($sourceFiles.Count)",
        "- Nodes: $($graph.nodes.Count)",
        "- Edges: $($graph.links.Count)",
        "- Communities: $communityCount",
        "- Built-at commit recorded by Graphify: ``$builtAtCommit``",
        "- Source fingerprint (SHA-256): ``$sourceFingerprint``",
        "",
        "The source fingerprint is computed from the exact files in the local Graphify",
        "manifest. ``graph.json`` and ``GRAPH_REPORT.md`` are derived navigation aids;",
        "source code, tests, accepted ADRs and authoritative architecture documents win",
        "whenever an inferred graph edge conflicts with repository evidence.",
        ""
    )
    $snapshotPath = Join-Path $repositoryRoot "graphify-out\SNAPSHOT.md"
    [System.IO.File]::WriteAllText(
        $snapshotPath,
        ($snapshotLines -join "`n"),
        [System.Text.UTF8Encoding]::new($false)
    )

    Write-Output (
        "Graphify snapshot ready: {0} files, {1} nodes, {2} edges, fingerprint {3}" -f
        $sourceFiles.Count,
        $graph.nodes.Count,
        $graph.links.Count,
        $sourceFingerprint
    )
}
finally {
    Pop-Location
}
