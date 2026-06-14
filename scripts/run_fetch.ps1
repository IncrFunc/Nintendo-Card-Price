param(
  [string]$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path,
  [string]$Python = "python",
  [string]$Config = "config.json",
  [switch]$DryRun
)

Set-Location $ProjectDir

$args = @("main.py", "--config", $Config, "fetch")
if ($DryRun) {
  $args += "--dry-run"
  $args += "--no-report"
}

& $Python @args
