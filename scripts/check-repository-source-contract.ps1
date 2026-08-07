[CmdletBinding()]
param(
    [string]$Root = "",
    [string]$PeerRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (!$Root) { $Root = Split-Path -Parent $PSScriptRoot }
$Root = [IO.Path]::GetFullPath($Root)

function Resolve-Descriptor([string]$RepositoryRoot) {
    foreach ($relative in @(
        "templates\mcp\boi-wiki-mcp-connection.json",
        "config\boi-wiki-mcp-connection.json"
    )) {
        $candidate = Join-Path $RepositoryRoot $relative
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    throw "MCP connection descriptor is missing: $RepositoryRoot"
}

function File-Hash([string]$Path) {
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required contract file is missing: $Path" }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$manifestPath = Join-Path $Root "repository-sources.json"
$selectorPath = Join-Path $Root "scripts\select-repository-source.ps1"
$connectorPath = Join-Path $Root "scripts\connect-boi-wiki-mcp.ps1"
$descriptorPath = Resolve-Descriptor $Root
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$descriptor = Get-Content -LiteralPath $descriptorPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$manifest.schema -cne "boi-repository-sources/v1") { throw "Invalid repository source manifest schema." }
if ([string]$descriptor.schema -cne "boi-wiki-mcp-connection/v1") { throw "Invalid MCP connection descriptor schema." }

$hashes = [ordered]@{
    manifest = File-Hash $manifestPath
    selector = File-Hash $selectorPath
    connector = File-Hash $connectorPath
    mcp_descriptor = File-Hash $descriptorPath
}
$peerState = "not-run"
if ($PeerRoot) {
    $PeerRoot = [IO.Path]::GetFullPath($PeerRoot)
    $peerHashes = [ordered]@{
        manifest = File-Hash (Join-Path $PeerRoot "repository-sources.json")
        selector = File-Hash (Join-Path $PeerRoot "scripts\select-repository-source.ps1")
        connector = File-Hash (Join-Path $PeerRoot "scripts\connect-boi-wiki-mcp.ps1")
        mcp_descriptor = File-Hash (Resolve-Descriptor $PeerRoot)
    }
    foreach ($name in $hashes.Keys) {
        if ($hashes[$name] -cne $peerHashes[$name]) { throw "Cross-repository contract hash mismatch: $name" }
    }
    $peerState = "matched"
}

[pscustomobject]@{
    schema = "boi-repository-source-contract-check/v1"
    ok = $true
    hashes = $hashes
    peer_check = $peerState
} | ConvertTo-Json -Depth 6
