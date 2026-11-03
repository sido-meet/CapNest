# 真实环境受控冒烟：往真实的 mcode / Claude Code skills 目录部署一个最小 skill，
# 验证两边一致，然后回滚。任何一步不符预期立即回滚，不留残留。
#
# 冒烟资产放在工作区之外的临时目录，不进入任何提交。

$ErrorActionPreference = "Stop"
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("capnest-smoke-" + [guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$ws = Join-Path $tmp "ws"
$src = Join-Path $tmp "capnest-smoke-test"

New-Item -ItemType Directory -Force -Path $src | Out-Null

$skillLines = @(
    "---",
    "name: capnest-smoke-test",
    "description: CapNest 第一刀的受控冒烟样本；验完即删除。",
    "---",
    "",
    "# CapNest Smoke Test",
    "",
    "这是一个只用于验证部署链路的最小 skill。回滚后不应留在任何 Agent 目录里。",
    ""
)
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $src "SKILL.md"), ($skillLines -join "`n"), $utf8)

function Invoke-Capnest {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & uv run capnest @Args
    return $LASTEXITCODE
}

$mcodeSkills = Join-Path $HOME ".minimax\skills"
$claudeSkills = Join-Path $HOME ".claude\skills"

function Snapshot {
    param([string]$Root)
    if (-not (Test-Path $Root)) { return @() }
    return Get-ChildItem -Recurse -File $Root | ForEach-Object { $_.FullName } | Sort-Object
}

$beforeMcode = Snapshot $mcodeSkills
$beforeClaude = Snapshot $claudeSkills

Write-Output "=== init / add / profile ==="
Invoke-Capnest init $ws
Invoke-Capnest --workspace $ws add skill $src
Invoke-Capnest --workspace $ws profile create smoke --asset skills/capnest-smoke-test --target mcode --target claude-code

Write-Output "=== plan ==="
Invoke-Capnest --workspace $ws plan --profile smoke --target mcode,claude-code

Write-Output "=== apply --yes ==="
Invoke-Capnest --workspace $ws apply --profile smoke --target mcode,claude-code --yes
Write-Output "apply exit=$LASTEXITCODE"

$mcodeFile = Join-Path $mcodeSkills "capnest-smoke-test\SKILL.md"
$claudeFile = Join-Path $claudeSkills "capnest-smoke-test\SKILL.md"

Write-Output "mcode  存在： $(Test-Path $mcodeFile)"
Write-Output "claude 存在： $(Test-Path $claudeFile)"

if (-not (Test-Path $mcodeFile)) { throw "mcode 侧没有部署成功" }
if (-not (Test-Path $claudeFile)) { throw "Claude Code 侧没有部署成功" }

$mcodeHash = (Get-FileHash $mcodeFile -Algorithm SHA256).Hash
$claudeHash = (Get-FileHash $claudeFile -Algorithm SHA256).Hash
Write-Output "两边哈希一致： $($mcodeHash -eq $claudeHash)"
if ($mcodeHash -ne $claudeHash) { throw "两边内容不一致" }

Write-Output "=== status ==="
Invoke-Capnest --workspace $ws status

Write-Output "=== rollback ==="
Invoke-Capnest --workspace $ws rollback --target mcode
Invoke-Capnest --workspace $ws rollback --target claude-code

$afterMcode = Snapshot $mcodeSkills
$afterClaude = Snapshot $claudeSkills

Write-Output "mcode 残留： $(Test-Path (Join-Path $mcodeSkills 'capnest-smoke-test'))"
Write-Output "claude 残留： $(Test-Path (Join-Path $claudeSkills 'capnest-smoke-test'))"

if (Compare-Object $beforeMcode $afterMcode) { throw "mcode 侧有残留差异" }
if (Compare-Object $beforeClaude $afterClaude) { throw "Claude Code 侧有残留差异" }

Write-Output "=== 冒烟通过：两边一致，且回滚后零残留 ==="
Remove-Item -Recurse -Force $tmp