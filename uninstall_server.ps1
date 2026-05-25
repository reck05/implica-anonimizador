# uninstall_server.ps1
# Desinstala el servicio del Implica Anonimizador.
# Ejecutar como administrador.

$TASK_NAME = "ImplicaAnonimizador"
$PORT = 8501

Write-Host "Deteniendo y eliminando tarea programada..." -ForegroundColor Yellow
Stop-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false -ErrorAction SilentlyContinue

Write-Host "Cerrando puerto $PORT en el firewall..." -ForegroundColor Yellow
Remove-NetFirewallRule -DisplayName "ImplicaAnonimizador-$PORT" -ErrorAction SilentlyContinue

Write-Host "Matando procesos streamlit residuales..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Write-Host ""
Write-Host "Desinstalado. La carpeta del proyecto y los mappings en projects/ NO se borran." -ForegroundColor Green
Write-Host "Si quieres eliminarlos también, borra manualmente esta carpeta."
