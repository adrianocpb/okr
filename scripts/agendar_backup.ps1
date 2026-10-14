# Registra (ou atualiza) uma tarefa diária no Agendador de Tarefas do Windows
# que executa scripts\backup.ps1. Roda com o usuário atual, sem privilégios elevados.
#
# Uso: powershell -ExecutionPolicy Bypass -File scripts\agendar_backup.ps1 [-Horario 12:30]
# Remover: Unregister-ScheduledTask -TaskName "OKR - Backup diario" -Confirm:$false
param(
    [string]$Horario = "12:30"
)
$ErrorActionPreference = "Stop"

$nomeTarefa = "OKR - Backup diario"
$script = Join-Path $PSScriptRoot "backup.ps1"

$acao = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$gatilho = New-ScheduledTaskTrigger -Daily -At $Horario
# StartWhenAvailable: se o computador estiver desligado no horário, executa assim que possível.
$opcoes = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName $nomeTarefa -Action $acao -Trigger $gatilho -Settings $opcoes `
    -Description "Backup diário criptografado do banco do sistema de OKRs." -Force | Out-Null

Write-Host "Tarefa '$nomeTarefa' registrada para todos os dias às $Horario."
