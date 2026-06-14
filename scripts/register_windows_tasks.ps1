param(
  [string]$TaskName = "NintendoGamePrice",
  [string]$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path,
  [string]$Python = "python",
  [string]$Config = "config.json"
)

$runScript = Join-Path $PSScriptRoot "run_fetch.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runScript`" -ProjectDir `"$ProjectDir`" -Python `"$Python`" -Config `"$Config`""
$triggerMorning = New-ScheduledTaskTrigger -Daily -At "10:00"
$triggerAfternoon = New-ScheduledTaskTrigger -Daily -At "16:00"

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerMorning, $triggerAfternoon) -Description "NintendoGamePrice compatibility task. Prefer: python main.py auto --ui --launch-edge" -Force
