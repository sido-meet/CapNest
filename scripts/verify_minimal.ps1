# 最小业务验证：严格按 docs/010 §7 的命令序列跑一遍，并逐条核验六条断言。
# 两个目标都指向临时目录，绝不碰真实 Agent 配置。

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("capnest-verify-" + [guid]::NewGuid().ToString("N"))

$ws = Join-Path $tmp "ws"
$mcode = Join-Path $tmp "mcode-home"
$claude = Join-Path $tmp "claude-home"
New-Item -ItemType Directory -Force -Path $mcode, $claude | Out-Null

$env:CAPNEST_TARGET_HOME_MCODE = $mcode
$env:CAPNEST_TARGET_HOME_CLAUDE_CODE = $claude

$pass = 0
$fail = 0
function Assert {
    param([bool]$Condition, [string]$Name, [string]$Detail)
    if ($Condition) {
        $script:pass++
        Write-Output ("  [PASS] " + $Name + "  " + $Detail)
    } else {
        $script:fail++
        Write-Output ("  [FAIL] " + $Name + "  " + $Detail)
    }
}

function Snapshot {
    param([string]$Root)
    if (-not (Test-Path $Root)) { return @() }
    return Get-ChildItem -Recurse -File $Root | ForEach-Object {
        $_.FullName.Substring($Root.Length) + "|" + (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    } | Sort-Object
}

Write-Output "=== docs/010 §7 的命令序列 ==="
uv run capnest init $ws;                    if ($LASTEXITCODE -ne 0) { throw "init 失败" }
uv run capnest --workspace $ws add skill (Join-Path $root "examples/data-agent/assets/skills/sql-analysis")
if ($LASTEXITCODE -ne 0) { throw "add 失败" }
uv run capnest --workspace $ws profile create data-agent --asset skills/sql-analysis --target mcode --target claude-code
if ($LASTEXITCODE -ne 0) { throw "profile create 失败" }
uv run capnest --workspace $ws plan   --profile data-agent --target mcode,claude-code
if ($LASTEXITCODE -ne 0) { throw "plan 失败" }
uv run capnest --workspace $ws apply  --profile data-agent --target mcode,claude-code --yes
if ($LASTEXITCODE -ne 0) { throw "apply 失败" }
uv run capnest --workspace $ws status
if ($LASTEXITCODE -ne 0) { throw "status 失败" }

Write-Output ""
Write-Output "=== 六条断言 ==="

# 断言 1：plan 之后目标目录逐字节不变
Write-Output "-- 断言 1：plan 是只读的"
$tmp2 = Join-Path $tmp "ws2"
New-Item -ItemType Directory -Force -Path $tmp2 | Out-Null
$ws2 = Join-Path $tmp2 "ws"
uv run capnest init $ws2 | Out-Null
uv run capnest --workspace $ws2 add skill (Join-Path $root "examples/data-agent/assets/skills/sql-analysis") | Out-Null
uv run capnest --workspace $ws2 profile create data-agent --asset skills/sql-analysis | Out-Null
$beforeM = Snapshot (Join-Path $mcode "skills")
$beforeC = Snapshot (Join-Path $claude "skills")
uv run capnest --workspace $ws2 plan --profile data-agent --target mcode,claude-code | Out-Null
$afterM = Snapshot (Join-Path $mcode "skills")
$afterC = Snapshot (Join-Path $claude "skills")
Assert (($beforeM -join "`n") -eq ($afterM -join "`n")) "plan 不改 mcode" ""
Assert (($beforeC -join "`n") -eq ($afterC -join "`n")) "plan 不改 claude-code" ""

# 断言 2：apply 之后两边都有该 skill，内容哈希与 assets/ 一致
Write-Output "-- 断言 2：apply 后两边内容一致且与 assets/ 一致"
$assetDir = Join-Path $ws "assets\skills\sql-analysis"
$assetHash = (Get-ChildItem -Recurse -File $assetDir | Sort-Object Name | ForEach-Object {
    $_.Name + "|" + (Get-FileHash $_.FullName -Algorithm SHA256).Hash }) -join "`n"
$mcodeDir = Join-Path $mcode "skills\sql-analysis"
$claudeDir = Join-Path $claude "skills\sql-analysis"
$mcodeHash = (Get-ChildItem -Recurse -File $mcodeDir | Sort-Object Name | ForEach-Object {
    $_.Name + "|" + (Get-FileHash $_.FullName -Algorithm SHA256).Hash }) -join "`n"
$claudeHash = (Get-ChildItem -Recurse -File $claudeDir | Sort-Object Name | ForEach-Object {
    $_.Name + "|" + (Get-FileHash $_.FullName -Algorithm SHA256).Hash }) -join "`n"
Assert (Test-Path $mcodeDir) "mcode 有该 skill" $mcodeDir
Assert (Test-Path $claudeDir) "claude-code 有该 skill" $claudeDir
Assert ($mcodeHash -eq $assetHash) "mcode 与 assets/ 一致" ""
Assert ($claudeHash -eq $assetHash) "claude-code 与 assets/ 一致" ""
Assert ($mcodeHash -eq $claudeHash) "两边完全相同" ""

# 断言 3：既有同名目录且不由 CapNest 管理 → 退出码 7，不覆盖
Write-Output "-- 断言 3：归属证明拒绝 unmanaged 路径"
$ws3 = Join-Path $tmp "ws3"
$m3 = Join-Path $tmp "m3-home"
New-Item -ItemType Directory -Force -Path $m3 | Out-Null
$env:CAPNEST_TARGET_HOME_MCODE = $m3
$env:CAPNEST_TARGET_HOME_CLAUDE_CODE = $claude
$intruder = Join-Path $m3 "skills\sql-analysis"
New-Item -ItemType Directory -Force -Path $intruder | Out-Null
Set-Content -Path (Join-Path $intruder "SKILL.md") -Value "别人的东西" -Encoding utf8NoBOM
$beforeIntruder = (Get-FileHash (Join-Path $intruder "SKILL.md") -Algorithm SHA256).Hash
uv run capnest init $ws3 | Out-Null
uv run capnest --workspace $ws3 add skill (Join-Path $root "examples/data-agent/assets/skills/sql-analysis") | Out-Null
uv run capnest --workspace $ws3 profile create data-agent --asset skills/sql-analysis | Out-Null
uv run capnest --workspace $ws3 apply --profile data-agent --target mcode --yes | Out-Null
$code = $LASTEXITCODE
$afterIntruder = (Get-FileHash (Join-Path $intruder "SKILL.md") -Algorithm SHA256).Hash
Assert ($code -eq 7) "退出码是 7" "实际 $code"
Assert ($beforeIntruder -eq $afterIntruder) "原有文件未被覆盖" ""

# 断言 4：重复 apply → 退出码 0，mtime 不变
Write-Output "-- 断言 4：重复 apply 幂等"
$env:CAPNEST_TARGET_HOME_MCODE = $mcode
$target = Join-Path $mcode "skills\sql-analysis\SKILL.md"
$mtimeBefore = (Get-Item $target).LastWriteTimeUtc.Ticks
uv run capnest --workspace $ws apply --profile data-agent --target mcode,claude-code --yes | Out-Null
$code = $LASTEXITCODE
$mtimeAfter = (Get-Item $target).LastWriteTimeUtc.Ticks
Assert ($code -eq 0) "退出码是 0" "实际 $code"
Assert ($mtimeBefore -eq $mtimeAfter) "mtime 不变" ""

# 断言 5：rollback 之后目标目录回到初始状态（逐字节）
Write-Output "-- 断言 5：rollback 回到初始状态"
$beforeRollbackM = Snapshot (Join-Path $mcode "skills")
$beforeRollbackC = Snapshot (Join-Path $claude "skills")
uv run capnest --workspace $ws rollback --target mcode | Out-Null
$codeM = $LASTEXITCODE
uv run capnest --workspace $ws rollback --target claude-code | Out-Null
$codeC = $LASTEXITCODE
$afterRollbackM = Snapshot (Join-Path $mcode "skills")
$afterRollbackC = Snapshot (Join-Path $claude "skills")
Assert ($codeM -eq 0 -and $codeC -eq 0) "两个目标回滚都成功" ""
Assert ($afterRollbackM.Count -eq 0) "mcode skills 目录清空" ""
Assert ($afterRollbackC.Count -eq 0) "claude-code skills 目录清空" ""

# 断言 6：任一步失败不留下半成品
Write-Output "-- 断言 6：失败不留半成品"
$ws4 = Join-Path $tmp "ws4"
$m4 = Join-Path $tmp "m4-home"
$c4 = Join-Path $tmp "c4-home"
New-Item -ItemType Directory -Force -Path $m4, $c4 | Out-Null
$env:CAPNEST_TARGET_HOME_MCODE = $m4
$env:CAPNEST_TARGET_HOME_CLAUDE_CODE = $c4
$blocker = Join-Path $c4 "skills\sql-analysis"
New-Item -ItemType Directory -Force -Path $blocker | Out-Null
Set-Content -Path (Join-Path $blocker "SKILL.md") -Value "别人的东西" -Encoding utf8NoBOM
uv run capnest init $ws4 | Out-Null
uv run capnest --workspace $ws4 add skill (Join-Path $root "examples/data-agent/assets/skills/sql-analysis") | Out-Null
uv run capnest --workspace $ws4 profile create data-agent --asset skills/sql-analysis | Out-Null
uv run capnest --workspace $ws4 apply --profile data-agent --target mcode,claude-code --yes | Out-Null
Assert ($LASTEXITCODE -eq 7) "整体失败" "退出码 $($LASTEXITCODE)"
Assert (-not (Test-Path (Join-Path $m4 "skills\sql-analysis"))) "mcode 侧没有半成品" ""
Assert ((Get-Content (Join-Path $blocker "SKILL.md") -Raw).Trim() -eq "别人的东西") "claude-code 侧原文件未动" ""

Write-Output ""
Write-Output ("=== 结果：$pass 通过 / $fail 失败 ===")
Remove-Item -Recurse -Force $tmp
if ($fail -gt 0) { exit 1 }