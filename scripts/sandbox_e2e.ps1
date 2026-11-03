# 第一刀的沙箱验收脚本：两个目标都指向临时目录，绝不碰真实配置。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path $root ".sandbox"

if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

$ws = Join-Path $tmp "ws"
$mcode = Join-Path $tmp "mcode-home"
$claude = Join-Path $tmp "claude-home"
New-Item -ItemType Directory -Force -Path $mcode, $claude | Out-Null

$env:CAPNEST_TARGET_HOME_MCODE = $mcode
$env:CAPNEST_TARGET_HOME_CLAUDE_CODE = $claude

function Invoke-Capnest {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & uv run capnest @Args
    return $LASTEXITCODE
}

Write-Output "=== init ==="
Invoke-Capnest init $ws

Write-Output "=== add ==="
Invoke-Capnest --workspace $ws add skill (Join-Path $root "examples/data-agent/assets/skills/sql-analysis")

Write-Output "=== profile create ==="
Invoke-Capnest --workspace $ws profile create data-agent --asset skills/sql-analysis --target mcode --target claude-code

Write-Output "=== plan（必须不写任何文件） ==="
Invoke-Capnest --workspace $ws plan --profile data-agent --target mcode,claude-code
Write-Output "plan exit=$LASTEXITCODE"
Write-Output "mcode skills 目录存在？ $(Test-Path (Join-Path $mcode 'skills'))"
Write-Output "claude skills 目录存在？ $(Test-Path (Join-Path $claude 'skills'))"

Write-Output "=== apply（无 --yes，应退出 5） ==="
Invoke-Capnest --workspace $ws apply --profile data-agent --target mcode,claude-code
Write-Output "apply exit=$LASTEXITCODE"

Write-Output "=== apply --yes ==="
Invoke-Capnest --workspace $ws apply --profile data-agent --target mcode,claude-code --yes
Write-Output "apply exit=$LASTEXITCODE"

Write-Output "=== 目标侧内容 ==="
Get-ChildItem -Recurse -File (Join-Path $mcode "skills") | ForEach-Object { $_.FullName }
Get-ChildItem -Recurse -File (Join-Path $claude "skills") | ForEach-Object { $_.FullName }

Write-Output "=== status ==="
Invoke-Capnest --workspace $ws status

Write-Output "=== rollback ==="
Invoke-Capnest --workspace $ws rollback --target mcode
Invoke-Capnest --workspace $ws rollback --target claude-code
Write-Output "rollback exit=$LASTEXITCODE"
Write-Output "mcode skills 目录存在？ $(Test-Path (Join-Path $mcode 'skills'))"
Write-Output "claude skills 目录存在？ $(Test-Path (Join-Path $claude 'skills'))"

