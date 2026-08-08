[CmdletBinding()]
param(
    [ValidateSet("Preview", "Apply", "Verify", "Resume", "Rollback")]
    [string]$Mode = "Preview",
    [ValidateSet("Auto", "Codex", "ClaudeCode")]
    [string]$Client = "Auto",
    [ValidateSet("Auto", "None", "ServiceToken", "OAuth")]
    [string]$AuthMode = "Auto",
    [string]$Endpoint = "",
    [string]$Root = "",
    [string]$DescriptorPath = "",
    [string]$ClientConfigRoot = "",
    [string]$TokenEnvVar = "",
    [string]$ConfirmPlanHash = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[void][Reflection.Assembly]::LoadWithPartialName("System.Net.Http")

function Hash-Text([string]$Value) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Value)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return (-join ($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") })) }
    finally { $sha.Dispose() }
}

function Safe-Endpoint([string]$Value) {
    if (!$Value) { return "" }
    try {
        $uri = [Uri]$Value
        $authority = $uri.Host
        if (!$uri.IsDefaultPort) { $authority = "{0}:{1}" -f $authority, $uri.Port }
        return "$($uri.Scheme)://$authority$($uri.AbsolutePath)"
    } catch { return "<configured-mcp-endpoint>" }
}

function Resolve-Endpoint {
    if ($Endpoint) { $candidate = $Endpoint }
    elseif ([Environment]::GetEnvironmentVariable([string]$descriptor.endpoint.external_url_env)) {
        $candidate = [Environment]::GetEnvironmentVariable([string]$descriptor.endpoint.external_url_env)
    } else {
        $candidate = ""
        $health = ([string]$descriptor.endpoint.local_default) -replace '/mcp$', '/health'
        try {
            $handler = [Net.Http.HttpClientHandler]::new()
            $http = [Net.Http.HttpClient]::new($handler)
            $http.Timeout = [TimeSpan]::FromSeconds(2)
            $response = $http.GetAsync($health).GetAwaiter().GetResult()
            if ($response.IsSuccessStatusCode) { $candidate = [string]$descriptor.endpoint.local_default }
            $http.Dispose()
            $handler.Dispose()
        } catch {}
    }
    if (!$candidate) { return "" }
    $candidate = $candidate.TrimEnd('/')
    if (!$candidate.EndsWith([string]$descriptor.endpoint.path)) {
        $candidate += [string]$descriptor.endpoint.path
    }
    try {
        $uri = [Uri]$candidate
        if ($uri.Scheme -notin @("http", "https")) { throw "unsupported scheme" }
        if ($uri.UserInfo -or $uri.Query -or $uri.Fragment) { throw "credentials or query are not allowed in the endpoint" }
    } catch { throw "MCP endpoint는 http 또는 https URL이어야 합니다." }
    return $candidate
}

function Toml-Escape([string]$Value) {
    return $Value.Replace('\', '\\').Replace('"', '\"')
}

function Managed-CodexBlock([string]$Url, [string]$EffectiveAuth) {
    $lines = @(
        "# boi-wiki-local:mcp-managed begin",
        "[mcp_servers.boi-wiki-mcp]",
        ('url = "' + (Toml-Escape $Url) + '"'),
        "enabled = true",
        "required = false",
        'default_tools_approval_mode = "writes"'
    )
    if ($EffectiveAuth -eq "ServiceToken") {
        $lines += ('bearer_token_env_var = "' + (Toml-Escape $TokenEnvVar) + '"')
    } elseif ($EffectiveAuth -eq "OAuth") {
        $lines += 'auth = "oauth"'
    }
    $lines += "# boi-wiki-local:mcp-managed end"
    return ($lines -join [Environment]::NewLine)
}

function Build-Preview {
    $resolvedEndpoint = Resolve-Endpoint
    $state = "preview-ready"; $pendingReason = ""; $blocker = ""; $action = "configure"
    if (!$resolvedEndpoint) {
        $state = "pending-external-system"; $pendingReason = "endpoint-required"; $blocker = "승인된 MCP endpoint 또는 BOI_WIKI_MCP_EXTERNAL_URL이 필요합니다."; $action = "blocked"
    }
    $effectiveAuth = $AuthMode
    if ($effectiveAuth -eq "Auto") {
        $effectiveAuth = if ([Environment]::GetEnvironmentVariable($TokenEnvVar)) { "ServiceToken" } else { "None" }
    }

    $beforeText = ""; $desiredText = ""; $target = ""
    if ($resolvedClient -eq "Codex") {
        $target = Join-Path $ClientConfigRoot "config.toml"
        if (Test-Path -LiteralPath $target -PathType Leaf) { $beforeText = [IO.File]::ReadAllText($target) }
        $begin = "# boi-wiki-local:mcp-managed begin"
        $end = "# boi-wiki-local:mcp-managed end"
        $unmanagedPattern = '(?m)^\[mcp_servers\.boi-wiki-mcp\]\s*$'
        if ($beforeText -match [regex]::Escape($begin)) {
            $pattern = '(?s)' + [regex]::Escape($begin) + '.*?' + [regex]::Escape($end)
            if ($beforeText -notmatch $pattern) {
                $state = "blocked-conflict"; $blocker = "기존 managed MCP block이 손상되었습니다."; $action = "blocked"
            } elseif ($resolvedEndpoint) {
                $desiredText = [regex]::Replace($beforeText, $pattern, (Managed-CodexBlock $resolvedEndpoint $effectiveAuth))
            }
        } elseif ($beforeText -match $unmanagedPattern) {
            $state = "blocked-conflict"; $blocker = "같은 이름의 unmanaged Codex MCP 설정이 있습니다. 자동 덮어쓰지 않습니다."; $action = "blocked"
        } elseif ($resolvedEndpoint) {
            $separator = if ($beforeText -and !$beforeText.EndsWith([Environment]::NewLine)) { [Environment]::NewLine } else { "" }
            $desiredText = $beforeText + $separator + (Managed-CodexBlock $resolvedEndpoint $effectiveAuth) + [Environment]::NewLine
        }
        if ($desiredText -and $desiredText -ceq $beforeText) { $state = "already-configured"; $action = "no-change" }
    } else {
        $target = "claude-code:user"
        if (!(Get-Command claude -ErrorAction SilentlyContinue)) {
            $state = "unsupported-client"; $blocker = "Claude Code CLI를 찾을 수 없습니다."; $action = "blocked"
        } elseif ($resolvedEndpoint) {
            $existing = @(& claude mcp get ([string]$descriptor.server_name) 2>$null)
            if ($LASTEXITCODE -eq 0) {
                $state = "blocked-conflict"; $blocker = "같은 이름의 Claude Code MCP 설정이 있습니다. 자동 덮어쓰지 않습니다."; $action = "blocked"
            }
        }
    }

    $beforeHash = Hash-Text $beforeText
    $desiredHash = if ($resolvedClient -eq "Codex" -and $desiredText) { Hash-Text $desiredText } else { "" }
    $plan = [ordered]@{
        schema = "boi-mcp-connection-plan/v1"; descriptor_sha256 = $descriptorHash
        client = $resolvedClient; endpoint = $resolvedEndpoint; auth_mode = $effectiveAuth
        token_env_var = if ($effectiveAuth -eq "ServiceToken") { $TokenEnvVar } else { "" }
        config_target = $target; before_hash = $beforeHash; desired_hash = $desiredHash
        state = $state; pending_reason = $pendingReason; action = $action; blocker = $blocker
    }
    $planHash = Hash-Text ($plan | ConvertTo-Json -Depth 8 -Compress)
    return [pscustomobject]@{
        schema = "boi-mcp-connection-preview/v1"; state = $state; pending_reason = $pendingReason; action = $action
        client = $resolvedClient; endpoint = Safe-Endpoint $resolvedEndpoint; auth_mode = $effectiveAuth
        token_env_var = if ($effectiveAuth -eq "ServiceToken") { $TokenEnvVar } else { "" }
        credential_present = if ($effectiveAuth -eq "ServiceToken") { [bool][Environment]::GetEnvironmentVariable($TokenEnvVar) } else { $null }
        config_target = $target; before_hash = $beforeHash; desired_hash = $desiredHash
        descriptor_sha256 = $descriptorHash; plan_hash = $planHash; blocker = $blocker
        restart_required = ($action -in @("configure", "no-change"))
        mutation_performed = $false; local_private_bytes_sent = 0
        repository_source_does_not_select_endpoint = $true
        _plan = $plan; _desired_text = $desiredText; _before_text = $beforeText
    }
}

function Parse-McpPayload([string]$Body) {
    $trimmed = $Body.Trim()
    if ($trimmed.StartsWith("{")) { return ($trimmed | ConvertFrom-Json) }
    foreach ($line in ($Body -split "\r?\n")) {
        if ($line.StartsWith("data:")) {
            $data = $line.Substring(5).Trim()
            if ($data.StartsWith("{")) { return ($data | ConvertFrom-Json) }
        }
    }
    throw "MCP 응답에서 JSON-RPC payload를 찾을 수 없습니다."
}

function Verify-Protocol([string]$Url, [string]$EffectiveAuth) {
    if (!$Url) {
        return [pscustomobject]@{ schema = "boi-mcp-connection-verification/v1"; ok = $false; state = "pending-external-system"; pending_reason = "endpoint-required"; local_private_bytes_sent = 0 }
    }
    $token = ""
    if ($EffectiveAuth -eq "ServiceToken") {
        $token = [Environment]::GetEnvironmentVariable($TokenEnvVar)
        if (!$token) {
            return [pscustomobject]@{ schema = "boi-mcp-connection-verification/v1"; ok = $false; state = "pending-external-system"; pending_reason = "auth-required"; token_env_var = $TokenEnvVar; local_private_bytes_sent = 0 }
        }
    }
    if ($EffectiveAuth -eq "OAuth") {
        return [pscustomobject]@{ schema = "boi-mcp-connection-verification/v1"; ok = $false; state = "pending-external-system"; pending_reason = "oauth-login-required"; local_private_bytes_sent = 0 }
    }
    $handler = [Net.Http.HttpClientHandler]::new()
    $http = [Net.Http.HttpClient]::new($handler)
    $http.Timeout = [TimeSpan]::FromSeconds(15)
    $http.DefaultRequestHeaders.Accept.ParseAdd("application/json")
    $http.DefaultRequestHeaders.Accept.ParseAdd("text/event-stream")
    if ($token) { $http.DefaultRequestHeaders.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $token) }
    try {
        $initialize = [ordered]@{
            jsonrpc = "2.0"; id = 1; method = "initialize"
            params = [ordered]@{
                protocolVersion = [string]$descriptor.verification.protocol_version
                capabilities = [ordered]@{}
                clientInfo = [ordered]@{ name = "boi-wiki-local-connection-check"; version = "1.0" }
            }
        } | ConvertTo-Json -Depth 8 -Compress
        $content = [Net.Http.StringContent]::new($initialize, [Text.Encoding]::UTF8, "application/json")
        $response = $http.PostAsync($Url, $content).GetAwaiter().GetResult()
        if ([int]$response.StatusCode -in @(401, 403)) {
            return [pscustomobject]@{ schema = "boi-mcp-connection-verification/v1"; ok = $false; state = "pending-external-system"; pending_reason = "auth-required"; token_env_var = $TokenEnvVar; local_private_bytes_sent = 0 }
        }
        if (!$response.IsSuccessStatusCode) {
            return [pscustomobject]@{ schema = "boi-mcp-connection-verification/v1"; ok = $false; state = "pending-external-system"; pending_reason = "connection-failed"; http_status = [int]$response.StatusCode; local_private_bytes_sent = 0 }
        }
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        [void](Parse-McpPayload $body)
        $sessionId = ""
        if ($response.Headers.Contains("Mcp-Session-Id")) { $sessionId = ($response.Headers.GetValues("Mcp-Session-Id") | Select-Object -First 1) }
        if ($sessionId) { $http.DefaultRequestHeaders.Add("Mcp-Session-Id", $sessionId) }
        $initialized = '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
        [void]$http.PostAsync($Url, [Net.Http.StringContent]::new($initialized, [Text.Encoding]::UTF8, "application/json")).GetAwaiter().GetResult()
        $listRequest = '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
        $listResponse = $http.PostAsync($Url, [Net.Http.StringContent]::new($listRequest, [Text.Encoding]::UTF8, "application/json")).GetAwaiter().GetResult()
        if (!$listResponse.IsSuccessStatusCode) {
            return [pscustomobject]@{ schema = "boi-mcp-connection-verification/v1"; ok = $false; state = "pending-external-system"; pending_reason = "tools-list-failed"; http_status = [int]$listResponse.StatusCode; local_private_bytes_sent = 0 }
        }
        $listPayload = Parse-McpPayload ($listResponse.Content.ReadAsStringAsync().GetAwaiter().GetResult())
        $tools = @($listPayload.result.tools | ForEach-Object { [string]$_.name })
        $required = @($descriptor.verification.required_tools | ForEach-Object { [string]$_ })
        $missing = @($required | Where-Object { $_ -notin $tools })
        return [pscustomobject]@{
            schema = "boi-mcp-connection-verification/v1"; ok = ($missing.Count -eq 0)
            state = if ($missing.Count -eq 0) { "verified" } else { "pending-external-system" }
            pending_reason = if ($missing.Count -eq 0) { "" } else { "required-tools-missing" }
            endpoint = Safe-Endpoint $Url; tools_count = $tools.Count; required_tools = $required
            missing_tools = $missing; local_private_bytes_sent = 0; write_tools_invoked = 0
        }
    } finally {
        $http.Dispose(); $handler.Dispose()
    }
}

if (!$Root) { $Root = Split-Path -Parent $PSScriptRoot }
$Root = [IO.Path]::GetFullPath($Root)
if (!$DescriptorPath) {
    $localDescriptor = Join-Path $Root "templates\mcp\boi-wiki-mcp-connection.json"
    $serverDescriptor = Join-Path $Root "config\boi-wiki-mcp-connection.json"
    $DescriptorPath = if (Test-Path -LiteralPath $localDescriptor -PathType Leaf) { $localDescriptor } else { $serverDescriptor }
}
if (!(Test-Path -LiteralPath $DescriptorPath -PathType Leaf)) { throw "MCP connection descriptor가 없습니다." }
$descriptorHash = (Get-FileHash -LiteralPath $DescriptorPath -Algorithm SHA256).Hash.ToLowerInvariant()
$descriptor = Get-Content -LiteralPath $DescriptorPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$descriptor.schema -cne "boi-wiki-mcp-connection/v1") { throw "MCP connection descriptor schema가 올바르지 않습니다." }
if (!$TokenEnvVar) { $TokenEnvVar = [string]$descriptor.authentication.service_token_env }
if ($Client -eq "Auto") {
    $Client = if (Test-Path -LiteralPath (Join-Path $env:USERPROFILE ".codex")) { "Codex" } elseif (Get-Command claude -ErrorAction SilentlyContinue) { "ClaudeCode" } else { "Codex" }
}
$resolvedClient = $Client
if (!$ClientConfigRoot) {
    $ClientConfigRoot = if ($resolvedClient -eq "Codex") { Join-Path $env:USERPROFILE ".codex" } else { Join-Path $env:USERPROFILE ".claude" }
}
$receiptDir = Join-Path $ClientConfigRoot ".boi"
$receiptPath = Join-Path $receiptDir "boi-wiki-mcp-receipt.json"

if ($Mode -eq "Verify" -or $Mode -eq "Resume") {
    $preview = Build-Preview
    $result = Verify-Protocol ([string]$preview._plan.endpoint) ([string]$preview._plan.auth_mode)
    $result | ConvertTo-Json -Depth 10
    if (!$result.ok) { exit 4 }
    exit 0
}

if ($Mode -eq "Rollback") {
    if (!(Test-Path -LiteralPath $receiptPath -PathType Leaf)) { throw "MCP rollback receipt가 없습니다." }
    $receipt = Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $rollbackPlan = [ordered]@{
        schema = "boi-mcp-connection-rollback-plan/v1"; client = [string]$receipt.client
        after_hash = [string]$receipt.after_hash; backup_path = [string]$receipt.backup_path
    }
    $rollbackHash = Hash-Text ($rollbackPlan | ConvertTo-Json -Depth 6 -Compress)
    if (!$ConfirmPlanHash) {
        [pscustomobject]@{ schema = "boi-mcp-connection-rollback-preview/v1"; client = [string]$receipt.client; plan_hash = $rollbackHash; mutation_performed = $false } | ConvertTo-Json
        exit 0
    }
    if ($ConfirmPlanHash -cne $rollbackHash) { throw "승인한 MCP rollback 계획이 일치하지 않습니다." }
    if ([string]$receipt.client -eq "Codex") {
        $target = [string]$receipt.config_target
        $current = if (Test-Path -LiteralPath $target -PathType Leaf) { [IO.File]::ReadAllText($target) } else { "" }
        if ((Hash-Text $current) -cne [string]$receipt.after_hash) { throw "Codex 설정이 적용 후 변경되어 자동 rollback할 수 없습니다." }
        if ([string]$receipt.backup_path) {
            [IO.File]::WriteAllText($target, [IO.File]::ReadAllText([string]$receipt.backup_path), [Text.UTF8Encoding]::new($false))
        } elseif (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target
        }
    } else {
        & claude mcp remove --scope user ([string]$descriptor.server_name)
        if ($LASTEXITCODE -ne 0) { throw "Claude Code MCP 설정 제거에 실패했습니다." }
    }
    $receipt.state = "rolled-back"
    $receipt | Add-Member -NotePropertyName rolled_back_at -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o")) -Force
    [IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
    [pscustomobject]@{ schema = "boi-mcp-connection-rollback-result/v1"; ok = $true; mutation_performed = $true } | ConvertTo-Json
    exit 0
}

$preview = Build-Preview
if ($Mode -eq "Preview") {
    ($preview | Select-Object * -ExcludeProperty _plan, _desired_text, _before_text) | ConvertTo-Json -Depth 10
    exit 0
}
if (!$ConfirmPlanHash -or $ConfirmPlanHash -cne $preview.plan_hash) {
    throw "승인한 MCP 설정 계획과 현재 설정·endpoint가 일치하지 않습니다. 새 preview가 필요합니다."
}
if ($preview.action -eq "blocked") { throw $preview.blocker }

$backupPath = ""
if ($resolvedClient -eq "Codex") {
    $target = [string]$preview._plan.config_target
    [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
    $current = if (Test-Path -LiteralPath $target -PathType Leaf) { [IO.File]::ReadAllText($target) } else { "" }
    if ((Hash-Text $current) -cne [string]$preview._plan.before_hash) { throw "Codex 설정이 preview 이후 변경되었습니다." }
    if ($current) {
        $backupDir = Join-Path $ClientConfigRoot "boi-backups"
        [IO.Directory]::CreateDirectory($backupDir) | Out-Null
        $backupPath = Join-Path $backupDir ("config-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".toml")
        [IO.File]::WriteAllText($backupPath, $current, [Text.UTF8Encoding]::new($false))
    }
    if ($preview.action -eq "configure") {
        $temp = "$target.boi.tmp"
        [IO.File]::WriteAllText($temp, [string]$preview._desired_text, [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temp -Destination $target -Force
    }
    $afterHash = Hash-Text ([IO.File]::ReadAllText($target))
} else {
    $arguments = @("mcp", "add", "--transport", "http", "--scope", "user", [string]$descriptor.server_name, [string]$preview._plan.endpoint)
    if ([string]$preview._plan.auth_mode -eq "ServiceToken") {
        $arguments += @("--header", ('Authorization: Bearer ${' + $TokenEnvVar + '}'))
    }
    & claude @arguments
    if ($LASTEXITCODE -ne 0) { throw "Claude Code MCP 설정에 실패했습니다." }
    $afterHash = ""
}
[IO.Directory]::CreateDirectory($receiptDir) | Out-Null
$receipt = [ordered]@{
    schema = "boi-mcp-connection-receipt/v1"; client = $resolvedClient
    descriptor_sha256 = $descriptorHash; plan_hash = [string]$preview.plan_hash
    endpoint = [string]$preview._plan.endpoint; auth_mode = [string]$preview._plan.auth_mode
    token_env_var = if ([string]$preview._plan.auth_mode -eq "ServiceToken") { $TokenEnvVar } else { "" }
    config_target = [string]$preview._plan.config_target; before_hash = [string]$preview._plan.before_hash
    after_hash = $afterHash; backup_path = $backupPath
    state = "configured-restart-required"; applied_at = (Get-Date).ToUniversalTime().ToString("o")
    local_private_bytes_sent = 0; external_fallback_is_not_push_approval = $true
}
[IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
[pscustomobject]@{
    schema = "boi-mcp-connection-apply-result/v1"; ok = $true
    state = "configured-restart-required"; client = $resolvedClient
    endpoint = Safe-Endpoint ([string]$preview._plan.endpoint); auth_mode = [string]$preview._plan.auth_mode
    plan_hash = [string]$preview.plan_hash; receipt = $receiptPath
    mutation_performed = ($preview.action -eq "configure"); local_private_bytes_sent = 0
} | ConvertTo-Json -Depth 8
