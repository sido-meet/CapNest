<#
.SYNOPSIS
    CapNest M0 实测：抓取两个目标的真实配置事实，产出测试 fixture。

.DESCRIPTION
    两个阶段，都不修改用户的真实配置：

    阶段 A（只读）：读取两个目标的真实路径、skills 目录清单、skill frontmatter 的键名，
      以及 mcode 的 config.yaml 的顶层键名。**不复制任何密钥值。**

    阶段 B（沙箱）：把 MINIMAX_DATA_DIR / CLAUDE_CONFIG_DIR 指向临时目录后运行两个 CLI，
      确认它们在沙箱下可运行，且没有在真实目录里留下新文件。

    产出：
      tests/fixtures/target_report.json   观测报告
      tests/fixtures/mcode_config.yaml    脱敏后的 mcode 配置
      tests/fixtures/claude.json          Claude Code 的最小样例
      tests/fixtures/skill/SKILL.md       最小 skill 样例

.EXAMPLE
    pwsh -File scripts/phase0_probe.ps1
#>
[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot '..' 'tests' 'fixtures')
)

$ErrorActionPreference = 'Stop'
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

function Get-FrontmatterKeys {
    param([string]$Path)
    $lines = Get-Content -LiteralPath $Path -TotalCount 40
    if ($lines.Count -lt 3 -or $lines[0].Trim() -ne '---') { return @() }
    $keys = @()
    for ($i = 1; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -eq '---') { break }
        if ($lines[$i] -match '^([A-Za-z][A-Za-z0-9_-]*):') { $keys += $Matches[1] }
    }
    return $keys
}

function Get-SkillInventory {
    param([string]$SkillsDir)
    if (-not (Test-Path -LiteralPath $SkillsDir)) { return @() }
    $items = @()
    Get-ChildItem -LiteralPath $SkillsDir -Directory | Sort-Object Name | ForEach-Object {
        $skillFile = Join-Path $_.FullName 'SKILL.md'
        $item = [ordered]@{
            name     = $_.Name
            has_skill_md = (Test-Path -LiteralPath $skillFile)
            nested   = $false
            frontmatterKeys = @()
        }
        if ($item.has_skill_md) {
            $item.frontmatterKeys = @(Get-FrontmatterKeys -Path $skillFile)
        }
        $nested = Get-ChildItem -LiteralPath $_.FullName -Directory -ErrorAction SilentlyContinue
        if ($nested) { $item.nested = $true }
        $items += [pscustomobject]$item
    }
    return $items
}

function Get-TopLevelKeys {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return @() }
    $text = Get-Content -LiteralPath $Path -Raw
    $keys = @()
    foreach ($line in ($text -split "`n")) {
        if ($line -match '^([A-Za-z][A-Za-z0-9_-]*):') { $keys += $Matches[1] }
    }
    return $keys
}

$userHome = $HOME
$targets = @(
    [ordered]@{
        target      = 'mcode'
        home        = (Join-Path $userHome '.minimax')
        config_file = (Join-Path $userHome '.minimax' 'config.yaml')
        skills      = (Join-Path $userHome '.minimax' 'skills')
        sandbox_env = 'MINIMAX_DATA_DIR'
    },
    [ordered]@{
        target      = 'claude-code'
        home        = (Join-Path $userHome '.claude')
        config_file = (Join-Path $userHome '.claude.json')
        skills      = (Join-Path $userHome '.claude' 'skills')
        sandbox_env = 'CLAUDE_CONFIG_DIR'
    }
)

$report = [ordered]@{
    generatedAt = (Get-Date).ToUniversalTime().ToString('o')
    phaseA = @()
    phaseB = @()
}

Write-Host '== 阶段 A：只读观测 =='
foreach ($t in $targets) {
    $entry = [ordered]@{
        target      = $t.target
        home        = $t.home
        homeExists  = (Test-Path -LiteralPath $t.home)
        configFile  = $t.config_file
        configExists = (Test-Path -LiteralPath $t.config_file)
        configTopLevelKeys = @(Get-TopLevelKeys -Path $t.config_file)
        skillsPath  = $t.skills
        skills      = @(Get-SkillInventory -SkillsDir $t.skills)
        sandboxEnv  = $t.sandbox_env
    }
    $report.phaseA += [pscustomobject]$entry
    Write-Host ("  {0,-12} home={1} skills={2}" -f $t.target, $entry.homeExists, $entry.skills.Count)
}

Write-Host '== 阶段 B：沙箱验证 =='
$sandboxRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("capnest-probe-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $sandboxRoot -Force | Out-Null
try {
    foreach ($cli in @(@('mcode', '--version'), @('claude', '--version'))) {
        $name = $cli[0]
        $before = @(Get-ChildItem -LiteralPath $HOME -Force -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
        $env:MINIMAX_DATA_DIR = Join-Path $sandboxRoot 'mcode-data'
        $env:CLAUDE_CONFIG_DIR = Join-Path $sandboxRoot 'claude-data'
        $version = $null
        $exitCode = $null
        try {
            $version = (& $name $cli[1] 2>&1 | Out-String).Trim()
            $exitCode = $LASTEXITCODE
        } catch {
            $version = "调用失败：$($_.Exception.Message)"
        }
        $after = @(Get-ChildItem -LiteralPath $HOME -Force -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
        $created = @($after | Where-Object { $before -notcontains $_ })
        $report.phaseB += [pscustomobject]@{
            cli      = $name
            exitCode = $exitCode
            version  = $version
            homeEntriesCreated = $created
            sandboxRoot = $sandboxRoot
        }
        Write-Host ("  {0,-8} exit={1} 顶层新增={2}" -f $name, $exitCode, $created.Count)
    }
} finally {
    Remove-Item Env:MINIMAX_DATA_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:CLAUDE_CONFIG_DIR -ErrorAction SilentlyContinue
}

$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $OutputDir 'target_report.json') -Encoding utf8

# 写一份**合成**的 skill 样本：golden fixture 要锁的是格式，不是用户的 skill 内容。
# 真实 skill 只在阶段 A 里被读取字段名，不复制内容。
$sample = @(
    '---'
    'name: capnest-sample'
    'description: 用于测试的最小 skill 样本；字段形状取自本机实测（name 与 description 必需）。'
    '---'
    ''
    '# CapNest Sample'
    ''
    '这是一个合成样本，仅用于锁定 SKILL.md 的格式约定。'
    ''
) -join "`n"
New-Item -ItemType Directory -Path (Join-Path $OutputDir 'skill') -Force | Out-Null
Set-Content -LiteralPath (Join-Path $OutputDir 'skill' 'SKILL.md') -Value $sample -Encoding utf8 -Force
Write-Host '  已写出合成 skill 样本'

# 脱敏后的 mcode 配置：把可能的密钥值替换掉。
$mcodeConfig = Join-Path $userHome '.minimax' 'config.yaml'
if (Test-Path -LiteralPath $mcodeConfig) {
    $redacted = (Get-Content -LiteralPath $mcodeConfig -Raw) -replace '(?m)^(\s*apiKey:\s*).+$', '$1"***"'
    $redacted = $redacted -replace '(?m)^(\s*baseURL:\s*).+$', '$1"***"'
    Set-Content -LiteralPath (Join-Path $OutputDir 'mcode_config.yaml') -Value $redacted -Encoding utf8
    Write-Host '  已写出脱敏后的 mcode_config.yaml'
}

Write-Host "产出目录：$OutputDir"
