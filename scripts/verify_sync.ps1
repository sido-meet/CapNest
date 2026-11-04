# 最小业务验证：改一处 → 两边同步 → 看见差异 → 一键还原。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("capnest-sync-" + [guid]::NewGuid().ToString("N"))
$ws = Join-Path $tmp "ws"
$mcode = Join-Path $tmp "mcode-home"
$claude = Join-Path $tmp "claude-home"
New-Item -ItemType Directory -Force -Path $mcode, $claude | Out-Null

$env:CAPNEST_TARGET_HOME_MCODE = $mcode
$env:CAPNEST_TARGET_HOME_CLAUDE_CODE = $claude

$utf8 = New-Object System.Text.UTF8Encoding $false

Write-Output "=== 1. 装一份 skill 到两个 Agent ==="
uv run capnest init $ws | Out-Null
uv run capnest --workspace $ws add skill (Join-Path $root "examples/data-agent/assets/skills/sql-analysis") | Out-Null
uv run capnest --workspace $ws profile create data-agent --asset skills/sql-analysis --target mcode --target claude-code | Out-Null
uv run capnest --workspace $ws apply --profile data-agent --target mcode,claude-code --yes | Out-Null
Write-Output "已部署。"

Write-Output ""
Write-Output "=== 2. 改资产（只改工作区这一处） ==="
$skill = Join-Path $ws "assets\skills\sql-analysis\SKILL.md"
$text = [System.IO.File]::ReadAllText($skill)
$text = $text.Replace("## 1. 读懂查询", "## 1. 读懂查询（v1.1 修订）")
[System.IO.File]::WriteAllText($skill, $text, $utf8)
Write-Output "已改：工作区 assets/skills/sql-analysis/SKILL.md"

Write-Output ""
Write-Output "=== 3. 同步前看到差异（plan） ==="
uv run capnest --workspace $ws plan --profile data-agent --target mcode,claude-code

Write-Output ""
Write-Output "=== 4. status：报版本落后 ==="
uv run capnest --workspace $ws status

Write-Output ""
Write-Output "=== 5. apply：两边同步 ==="
uv run capnest --workspace $ws apply --profile data-agent --target mcode,claude-code --yes | Out-Null
$mcodeText = [System.IO.File]::ReadAllText((Join-Path $mcode "skills\sql-analysis\SKILL.md"))
$claudeText = [System.IO.File]::ReadAllText((Join-Path $claude "skills\sql-analysis\SKILL.md"))
Write-Output ("mcode 已同步新内容： " + $mcodeText.Contains("v1.1 修订"))
Write-Output ("claude-code 已同步新内容： " + $claudeText.Contains("v1.1 修订"))
Write-Output ("两边完全一致： " + ($mcodeText -eq $claudeText))
uv run capnest --workspace $ws status

Write-Output ""
Write-Output "=== 6. 出问题一键还原（rollback） ==="
uv run capnest --workspace $ws rollback --target mcode | Out-Null
$restored = [System.IO.File]::ReadAllText((Join-Path $mcode "skills\sql-analysis\SKILL.md"))
Write-Output ("mcode 已还原为旧内容： " + (-not $restored.Contains("v1.1 修订")))

Remove-Item -Recurse -Force $tmp