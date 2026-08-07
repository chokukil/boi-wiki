[CmdletBinding()]
param(
    [ValidateSet("Detect", "Preview", "Apply", "Verify", "Resume", "Rollback")]
    [string]$Mode = "Preview",
    [string]$Root = "",
    [string]$RepositoryId = "",
    [string]$ManifestPath = "",
    [string]$ConfirmPlanHash = "",
    [int]$ProbeTimeoutSeconds = 0,
    [int]$NetworkRetryCount = -1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Hash-Text([string]$Value) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Value)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return (-join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") })) }
    finally { $sha.Dispose() }
}

function Safe-Remote([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    if ($Value -match '^[A-Za-z][A-Za-z0-9+.-]*://') {
        try {
            $uri = [Uri]$Value
            $authority = $uri.Host
            if (!$uri.IsDefaultPort) { $authority = "{0}:{1}" -f $authority, $uri.Port }
            if ($uri.Scheme -eq "ssh" -and $uri.UserInfo -eq "git") { $authority = "git@$authority" }
            return "$($uri.Scheme)://$authority$($uri.PathAndQuery)"
        } catch { return "<configured-origin>" }
    }
    return $Value
}

function Git-Value([string[]]$Arguments, [switch]$AllowFailure) {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $output = @(& git -C $Root @Arguments 2>$null)
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if (!$AllowFailure -and $code -ne 0) { throw "Git command failed: $($Arguments[0])" }
    return [pscustomobject]@{ Code = $code; Text = (($output -join [Environment]::NewLine).Trim()) }
}

function Invoke-RemoteProbe([string]$Url, [int]$TimeoutSeconds, [int]$Retries) {
    $attempts = @()
    for ($attempt = 1; $attempt -le ($Retries + 1); $attempt++) {
        $psi = [Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = (Get-Command git -ErrorAction Stop).Source
        $psi.Arguments = 'ls-remote --symref "' + $Url.Replace('"', '\"') + '" HEAD'
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $psi.EnvironmentVariables["GIT_TERMINAL_PROMPT"] = "0"
        $psi.EnvironmentVariables["GCM_INTERACTIVE"] = "Never"
        $process = [Diagnostics.Process]::new()
        $process.StartInfo = $psi
        [void]$process.Start()
        $finished = $process.WaitForExit($TimeoutSeconds * 1000)
        if (!$finished) {
            try { $process.Kill() } catch {}
            $classification = "network-unreachable"
            $errorKind = "timeout"
            $attempts += [pscustomobject]@{ attempt = $attempt; result = $errorKind; exit_code = -1 }
        } else {
            $stdout = $process.StandardOutput.ReadToEnd()
            $stderr = $process.StandardError.ReadToEnd()
            $combined = ($stdout + [Environment]::NewLine + $stderr).ToLowerInvariant()
            if ($process.ExitCode -eq 0 -and $stdout -match '(?m)^([0-9a-f]{40,64})\s+HEAD\s*$') {
                $revision = $Matches[1]
                $headRef = ""
                if ($stdout -match '(?m)^ref:\s+refs/heads/([^\s]+)\s+HEAD\s*$') { $headRef = $Matches[1] }
                $attempts += [pscustomobject]@{ attempt = $attempt; result = "readable"; exit_code = 0 }
                return [pscustomobject]@{
                    classification = "readable"; error_kind = ""; revision = $revision
                    head_ref = $headRef; attempts = $attempts
                }
            }
            $authPattern = 'authentication failed|authorization failed|could not read username|terminal prompts disabled|access denied|permission denied|repository not found|not authorized|http[^\r\n]*(401|403)'
            $networkPattern = 'could not resolve host|no such host|network is unreachable|failed to connect|connection refused|connection timed out|operation timed out|could not connect|connection was reset'
            if ($combined -match $authPattern) {
                $classification = "auth-or-access-required"
                $errorKind = "authentication-or-repository-access"
            } elseif ($combined -match $networkPattern) {
                $classification = "network-unreachable"
                if ($combined -match 'resolve host|no such host') { $errorKind = "dns-failure" }
                elseif ($combined -match 'refused') { $errorKind = "connection-refused" }
                elseif ($combined -match 'timed out') { $errorKind = "timeout" }
                else { $errorKind = "network-unreachable" }
            } else {
                $classification = "auth-or-access-required"
                $errorKind = "unclassified-repository-access"
            }
            $attempts += [pscustomobject]@{ attempt = $attempt; result = $errorKind; exit_code = $process.ExitCode }
        }
        if ($classification -ne "network-unreachable" -or $attempt -gt $Retries) { break }
    }
    return [pscustomobject]@{
        classification = $classification; error_kind = $errorKind
        revision = ""; head_ref = ""; attempts = $attempts
    }
}

function Resolve-RepositoryId($Manifest) {
    if ($RepositoryId) {
        if ($null -eq $Manifest.repositories.$RepositoryId) { throw "Unknown repository id: $RepositoryId" }
        return $RepositoryId
    }
    foreach ($property in $Manifest.repositories.PSObject.Properties) {
        $matches = $true
        foreach ($marker in @($property.Value.markers)) {
            if (!(Test-Path -LiteralPath (Join-Path $Root ([string]$marker)))) { $matches = $false; break }
        }
        if ($matches) { return [string]$property.Name }
    }
    throw "현재 checkout의 repository id를 확인할 수 없습니다."
}

function Current-Origin {
    $fetch = Git-Value @("remote", "get-url", "origin") -AllowFailure
    $push = Git-Value @("remote", "get-url", "--push", "origin") -AllowFailure
    return [pscustomobject]@{
        exists = ($fetch.Code -eq 0 -and $fetch.Text)
        fetch = if ($fetch.Code -eq 0) { $fetch.Text } else { "" }
        push = if ($push.Code -eq 0) { $push.Text } else { "" }
    }
}

function Test-CandidateContainsCached([string]$CandidateUrl, [string]$Branch, [string]$CachedRevision, [string]$CandidateRevision) {
    $temporary = Join-Path ([IO.Path]::GetTempPath()) ("boi-mirror-check-" + [guid]::NewGuid().ToString("N"))
    [IO.Directory]::CreateDirectory($temporary) | Out-Null
    $previousPreference = $ErrorActionPreference
    $previousPrompt = $env:GIT_TERMINAL_PROMPT
    $previousInteractive = $env:GCM_INTERACTIVE
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $env:GIT_TERMINAL_PROMPT = "0"
        $env:GCM_INTERACTIVE = "Never"
        & git init --bare $temporary 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { return $false }
        & git -C $temporary fetch --quiet --no-tags $Root $CachedRevision 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        & git -C $temporary fetch --quiet --no-tags $CandidateUrl ("refs/heads/" + $Branch) 2>$null
        if ($LASTEXITCODE -ne 0) { return $false }
        & git -C $temporary merge-base --is-ancestor $CachedRevision $CandidateRevision 2>$null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $previousPreference
        $env:GIT_TERMINAL_PROMPT = $previousPrompt
        $env:GCM_INTERACTIVE = $previousInteractive
        if (Test-Path -LiteralPath $temporary -PathType Container) {
            Remove-Item -LiteralPath $temporary -Recurse -Force
        }
    }
}

function Build-Preview {
    $repo = $manifest.repositories.$resolvedRepositoryId
    $internal = Invoke-RemoteProbe ([string]$repo.internal_url) $ProbeTimeoutSeconds $NetworkRetryCount
    $external = $null
    $state = ""; $reason = ""; $selected = ""; $revision = ""
    $headRef = [string]$repo.stable_branch
    $blocker = ""

    if ($internal.classification -eq "readable") {
        $state = "internal-readable"; $reason = "internal-readable"
        $selected = [string]$repo.internal_url; $revision = [string]$internal.revision
        if ($internal.head_ref) { $headRef = [string]$internal.head_ref }
    } elseif ($internal.classification -eq "auth-or-access-required") {
        $state = "internal-auth-or-repository-access-required"
        $reason = [string]$internal.error_kind
        $blocker = "Bitbucket 로그인과 BOI 프로젝트의 '$resolvedRepositoryId' 저장소 Read 권한을 확인하세요."
    } else {
        $external = Invoke-RemoteProbe ([string]$repo.external_url) $ProbeTimeoutSeconds 0
        if ($external.classification -eq "readable") {
            $state = "external-readable"; $reason = "internal-unreachable-external-readable"
            $selected = [string]$repo.external_url; $revision = [string]$external.revision
            if ($external.head_ref) { $headRef = [string]$external.head_ref }
        } else {
            $state = if ($currentOrigin.exists) { "offline-existing" } else { "source-unavailable" }
            $reason = "internal-and-external-unavailable"
            $blocker = if ($currentOrigin.exists) {
                "현재 checkout을 Local-only로 사용할 수 있지만 clone과 update는 네트워크 복구 전까지 중단됩니다."
            } else { "사내 Bitbucket과 사외 GitHub 저장소를 모두 읽을 수 없습니다." }
        }
    }

    $action = "no-change"; $mirrorStatus = "not-required"
    if ($blocker) {
        $action = "blocked"
    } elseif (!$currentOrigin.exists -or $currentOrigin.fetch -cne $selected -or $currentOrigin.push -cne $selected) {
        $action = "set-origin"
        $approvedUrls = @([string]$repo.internal_url, [string]$repo.external_url)
        if ($currentOrigin.exists -and $currentOrigin.fetch -in $approvedUrls) {
            $cached = Git-Value @("rev-parse", "refs/remotes/origin/$headRef") -AllowFailure
            if ($cached.Code -eq 0 -and $cached.Text -match '^[0-9a-f]{40,64}$') {
                if ($cached.Text -cne $revision) {
                    if (Test-CandidateContainsCached $selected $headRef $cached.Text $revision) {
                        $mirrorStatus = "candidate-contains-current-stable"
                    } else {
                        $action = "blocked"; $state = "mirror-sync-required"
                        $mirrorStatus = "stable-history-diverged-or-incomplete"
                        $blocker = "후보 저장소의 ${headRef} history가 현재 승인된 origin/${headRef} commit을 포함하지 않습니다. mirror 동기화를 먼저 확인하세요."
                    }
                } else { $mirrorStatus = "stable-revision-equal" }
            } else { $mirrorStatus = "no-cached-stable-ref" }
        }
    }

    $plan = [ordered]@{
        schema = "boi-repository-source-plan/v1"; repository_id = $resolvedRepositoryId
        manifest_sha256 = $manifestHash
        current_origin_fingerprint = Hash-Text (($currentOrigin.fetch + [Environment]::NewLine + $currentOrigin.push))
        selected_origin = $selected; state = $state; selection_reason = $reason
        stable_branch = $headRef; remote_revision = $revision; action = $action
        mirror_status = $mirrorStatus; blocker = $blocker
    }
    $planHash = Hash-Text ($plan | ConvertTo-Json -Depth 8 -Compress)
    return [pscustomobject]@{
        schema = "boi-repository-source-preview/v1"; repository_id = $resolvedRepositoryId
        state = $state; action = $action; selection_reason = $reason
        current_origin = [pscustomobject]@{ fetch = Safe-Remote $currentOrigin.fetch; push = Safe-Remote $currentOrigin.push }
        selected_origin = Safe-Remote $selected; stable_branch = $headRef
        remote_revision = $revision; mirror_status = $mirrorStatus; blocker = $blocker
        probes = [pscustomobject]@{ internal = $internal; external = $external }
        manifest_sha256 = $manifestHash; plan_hash = $planHash; mutation_performed = $false
        external_fallback_is_not_push_approval = $true; mcp_endpoint_selected = $false
        _plan = $plan
    }
}

function Public-Result($Value) {
    return (($Value | Select-Object * -ExcludeProperty _plan) | ConvertTo-Json -Depth 12)
}

if (!$Root) { $Root = Split-Path -Parent $PSScriptRoot }
$Root = [IO.Path]::GetFullPath($Root)
if (!(Test-Path -LiteralPath (Join-Path $Root ".git"))) { throw "Git checkout이 아닙니다: $Root" }
if (!(Get-Command git -ErrorAction SilentlyContinue)) { throw "Git for Windows가 필요합니다." }
if (!$ManifestPath) { $ManifestPath = Join-Path $Root "repository-sources.json" }
if (!(Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "repository source manifest가 없습니다." }
$manifestHash = (Get-FileHash -LiteralPath $ManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$manifest.schema -cne "boi-repository-sources/v1") { throw "repository source manifest schema가 올바르지 않습니다." }
$resolvedRepositoryId = Resolve-RepositoryId $manifest
if ($ProbeTimeoutSeconds -le 0) { $ProbeTimeoutSeconds = [int]$manifest.probe.timeout_seconds }
if ($NetworkRetryCount -lt 0) { $NetworkRetryCount = [int]$manifest.probe.network_retry_count }
$currentOrigin = Current-Origin

$gitDir = (Git-Value @("rev-parse", "--git-dir")).Text
if (![IO.Path]::IsPathRooted($gitDir)) { $gitDir = Join-Path $Root $gitDir }
$receiptDir = Join-Path $gitDir "boi"
$receiptPath = Join-Path $receiptDir "repository-source.json"

if ($Mode -eq "Rollback") {
    if (!(Test-Path -LiteralPath $receiptPath -PathType Leaf)) { throw "rollback receipt가 없습니다." }
    $receipt = Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $rollbackPlan = [ordered]@{
        schema = "boi-repository-source-rollback-plan/v1"; repository_id = [string]$receipt.repository_id
        current_origin_fingerprint = Hash-Text (($currentOrigin.fetch + [Environment]::NewLine + $currentOrigin.push))
        expected_origin_fingerprint = [string]$receipt.after_origin_fingerprint
        restore_fetch = [string]$receipt.previous_origin.fetch; restore_push = [string]$receipt.previous_origin.push
    }
    $rollbackHash = Hash-Text ($rollbackPlan | ConvertTo-Json -Depth 6 -Compress)
    if (!$ConfirmPlanHash) {
        [pscustomobject]@{
            schema = "boi-repository-source-rollback-preview/v1"; repository_id = [string]$receipt.repository_id
            current_origin = [pscustomobject]@{ fetch = Safe-Remote $currentOrigin.fetch; push = Safe-Remote $currentOrigin.push }
            restore_origin = [pscustomobject]@{ fetch = Safe-Remote $rollbackPlan.restore_fetch; push = Safe-Remote $rollbackPlan.restore_push }
            plan_hash = $rollbackHash; mutation_performed = $false
        } | ConvertTo-Json -Depth 8
        exit 0
    }
    if ($ConfirmPlanHash -cne $rollbackHash) { throw "승인한 rollback 계획과 현재 상태가 일치하지 않습니다." }
    if ($rollbackPlan.current_origin_fingerprint -cne $rollbackPlan.expected_origin_fingerprint) {
        throw "origin이 적용 이후 변경되어 자동 rollback할 수 없습니다."
    }
    if ($rollbackPlan.restore_fetch) {
        if ($currentOrigin.exists) { & git -C $Root remote set-url origin $rollbackPlan.restore_fetch }
        else { & git -C $Root remote add origin $rollbackPlan.restore_fetch }
        if ($LASTEXITCODE -ne 0) { throw "origin fetch URL 복원에 실패했습니다." }
        & git -C $Root config --unset-all remote.origin.pushurl 2>$null
        if ($rollbackPlan.restore_push -and $rollbackPlan.restore_push -cne $rollbackPlan.restore_fetch) {
            & git -C $Root remote set-url --add --push origin $rollbackPlan.restore_push
            if ($LASTEXITCODE -ne 0) { throw "origin push URL 복원에 실패했습니다." }
        }
    } elseif ($currentOrigin.exists) {
        & git -C $Root remote remove origin
        if ($LASTEXITCODE -ne 0) { throw "origin 제거에 실패했습니다." }
    }
    $receipt.state = "rolled-back"
    $receipt | Add-Member -NotePropertyName rolled_back_at -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o")) -Force
    [IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
    [pscustomobject]@{ schema = "boi-repository-source-rollback-result/v1"; ok = $true; mutation_performed = $true } | ConvertTo-Json
    exit 0
}

if ($Mode -eq "Verify" -or $Mode -eq "Resume") {
    if ($Mode -eq "Resume" -and !(Test-Path -LiteralPath $receiptPath -PathType Leaf)) {
        Public-Result (Build-Preview)
        exit 0
    }
    $expected = ""
    $receipt = $null
    if (Test-Path -LiteralPath $receiptPath -PathType Leaf) {
        $receipt = Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $expected = [string]$receipt.selected_origin
    }
    $ok = $currentOrigin.exists -and (!$expected -or ($currentOrigin.fetch -ceq $expected -and $currentOrigin.push -ceq $expected))
    [pscustomobject]@{
        schema = "boi-repository-source-verification/v1"; ok = $ok
        repository_id = $resolvedRepositoryId
        current_origin = [pscustomobject]@{ fetch = Safe-Remote $currentOrigin.fetch; push = Safe-Remote $currentOrigin.push }
        expected_origin = Safe-Remote $expected
        stable_branch = if ($receipt) { [string]$receipt.stable_branch } else { [string]$manifest.repositories.$resolvedRepositoryId.stable_branch }
        remote_revision = if ($receipt) { [string]$receipt.remote_revision } else { "" }
        mcp_endpoint_selected = $false
    } | ConvertTo-Json -Depth 8
    if (!$ok) { exit 4 }
    exit 0
}

$preview = Build-Preview
if ($Mode -eq "Detect") { $preview.schema = "boi-repository-source-detection/v1" }
if ($Mode -in @("Detect", "Preview")) {
    Public-Result $preview
    exit 0
}
if (!$ConfirmPlanHash -or $ConfirmPlanHash -cne $preview.plan_hash) {
    throw "승인한 source 선택 계획과 현재 probe·origin 상태가 일치하지 않습니다. 새 preview가 필요합니다."
}
if ($preview.action -eq "blocked") { throw $preview.blocker }

$before = $currentOrigin
if ($preview.action -eq "set-origin") {
    $target = [string]$preview._plan.selected_origin
    if ($currentOrigin.exists) { & git -C $Root remote set-url origin $target }
    else { & git -C $Root remote add origin $target }
    if ($LASTEXITCODE -ne 0) { throw "origin fetch URL 변경에 실패했습니다." }
    & git -C $Root config --unset-all remote.origin.pushurl 2>$null
    & git -C $Root remote set-url --add --push origin $target
    if ($LASTEXITCODE -ne 0) { throw "origin push URL 변경에 실패했습니다." }
}
$after = Current-Origin
$targetOrigin = [string]$preview._plan.selected_origin
if ($targetOrigin -and ($after.fetch -cne $targetOrigin -or $after.push -cne $targetOrigin)) {
    throw "origin 변경 후 검증에 실패했습니다."
}
[IO.Directory]::CreateDirectory($receiptDir) | Out-Null
$receipt = [ordered]@{
    schema = "boi-repository-source-receipt/v1"; repository_id = $resolvedRepositoryId
    manifest_sha256 = $manifestHash; plan_hash = [string]$preview.plan_hash
    state = [string]$preview.state
    previous_origin = [ordered]@{ fetch = $before.fetch; push = $before.push }
    selected_origin = $targetOrigin
    after_origin_fingerprint = Hash-Text (($after.fetch + [Environment]::NewLine + $after.push))
    remote_revision = [string]$preview.remote_revision
    stable_branch = [string]$preview.stable_branch
    applied_at = (Get-Date).ToUniversalTime().ToString("o")
    external_fallback_is_not_push_approval = $true; mcp_endpoint_selected = $false
}
[IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
[pscustomobject]@{
    schema = "boi-repository-source-apply-result/v1"; ok = $true
    repository_id = $resolvedRepositoryId; state = [string]$preview.state
    origin = Safe-Remote $targetOrigin; plan_hash = [string]$preview.plan_hash
    mutation_performed = ($preview.action -eq "set-origin")
    receipt = ".git/boi/repository-source.json"
    external_fallback_is_not_push_approval = $true; mcp_endpoint_selected = $false
} | ConvertTo-Json -Depth 8
