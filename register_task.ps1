# 한국증시 수급 브리핑 - 윈도우 작업 스케줄러 등록
# 사용: PowerShell 에서  .\register_task.ps1   실행 (관리자 권한 불필요, 현재 사용자 기준)
# 평일(월~금) 오전 6시에 run_daily.bat 실행.

$ErrorActionPreference = "Stop"
$here    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$bat     = Join-Path $here "run_daily.bat"
$taskName = "KRMarketBriefing"

if (-not (Test-Path $bat)) { throw "run_daily.bat 를 찾을 수 없습니다: $bat" }

$action  = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 6:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
            -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 3)

# 기존 동일 이름 작업이 있으면 교체
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "한국증시 외국인/기관/개인 수급 + 나스닥 영향 브리핑 (매 평일 06:00, 카카오 발송)" | Out-Null

Write-Host "[완료] '$taskName' 작업이 등록되었습니다 (평일 06:00)."
Write-Host "확인:  Get-ScheduledTask -TaskName $taskName"
Write-Host "즉시 테스트:  Start-ScheduledTask -TaskName $taskName   (그 후 reports\run.log 확인)"
Write-Host "해제:  Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
