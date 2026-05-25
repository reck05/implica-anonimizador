# install_server.ps1
# Instalador del Implica Anonimizador para el servidor de oficina.
# Ejecutar como administrador (clic derecho > Ejecutar con PowerShell).
#
# Lo que hace:
#   1. Verifica Python 3.11+
#   2. Crea un entorno virtual en .venv\
#   3. Instala todas las dependencias
#   4. Descarga el modelo spaCy en español
#   5. Configura una tarea programada para arrancar al boot
#   6. Abre el puerto 8501 en el firewall
#   7. Arranca el servicio
#
# Configuración (puedes cambiarla en este archivo antes de ejecutar):
$PORT = 8501
$PASSWORD = "implica2026"                          # cambiar antes de instalar
$INSTALL_DIR = $PSScriptRoot                       # carpeta donde está este script
$TASK_NAME = "ImplicaAnonimizador"

# ----------- No tocar a partir de aquí -----------

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Implica Anonimizador - Instalador" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Carpeta: $INSTALL_DIR"
Write-Host "Puerto:  $PORT"
Write-Host ""

# --- 1) Verificar Python ---
Write-Host "[1/7] Verificando Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "      OK: $pyVersion"
} catch {
    Write-Host "      ERROR: Python no encontrado." -ForegroundColor Red
    Write-Host "      Descárgalo de https://www.python.org/downloads/ (3.11 o superior)"
    Write-Host "      IMPORTANTE: marca 'Add Python to PATH' al instalar."
    exit 1
}

# --- 2) Crear venv ---
Write-Host "[2/7] Creando entorno virtual en .venv\..." -ForegroundColor Yellow
if (Test-Path "$INSTALL_DIR\.venv") {
    Write-Host "      .venv ya existe, se reutiliza"
} else {
    python -m venv "$INSTALL_DIR\.venv"
    Write-Host "      OK"
}

$venvPython = "$INSTALL_DIR\.venv\Scripts\python.exe"
$venvStreamlit = "$INSTALL_DIR\.venv\Scripts\streamlit.exe"

# --- 3) Instalar dependencias ---
Write-Host "[3/7] Instalando dependencias (tarda un par de minutos)..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -e "$INSTALL_DIR" --quiet
& $venvPython -m pip install streamlit pandas --quiet
Write-Host "      OK"

# --- 4) Modelo spaCy ---
Write-Host "[4/7] Descargando modelo de NLP en español (40MB)..." -ForegroundColor Yellow
& $venvPython -m spacy download es_core_news_md --quiet
Write-Host "      OK"

# --- 5) Firewall ---
Write-Host "[5/7] Abriendo puerto $PORT en el firewall..." -ForegroundColor Yellow
$existing = Get-NetFirewallRule -DisplayName "ImplicaAnonimizador-$PORT" -ErrorAction SilentlyContinue
if ($existing) {
    Remove-NetFirewallRule -DisplayName "ImplicaAnonimizador-$PORT" -ErrorAction SilentlyContinue
}
New-NetFirewallRule `
    -DisplayName "ImplicaAnonimizador-$PORT" `
    -Direction Inbound `
    -LocalPort $PORT `
    -Protocol TCP `
    -Action Allow `
    -Profile Domain,Private | Out-Null
Write-Host "      OK (solo red local, no Internet)"

# --- 6) Tarea programada de arranque ---
Write-Host "[6/7] Configurando arranque automático..." -ForegroundColor Yellow

# Crear el script de arranque
$startScript = @"
`$env:IMPLICA_ANON_PASSWORD = '$PASSWORD'
& '$venvStreamlit' run '$INSTALL_DIR\streamlit_app.py' ``
    --server.address 0.0.0.0 ``
    --server.port $PORT ``
    --server.headless true ``
    --browser.gatherUsageStats false
"@
$startScript | Out-File -FilePath "$INSTALL_DIR\start_server.ps1" -Encoding utf8 -Force

# Eliminar tarea previa si existe
Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:`$false -ErrorAction SilentlyContinue

# Crear tarea
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$INSTALL_DIR\start_server.ps1`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TASK_NAME `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Implica Anonimizador - Servidor Streamlit interno" | Out-Null

Write-Host "      OK (arranca solo al encender el servidor)"

# --- 7) Arrancar ahora ---
Write-Host "[7/7] Arrancando el servicio..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName $TASK_NAME
Start-Sleep -Seconds 5

# Verificar
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$PORT/_stcore/health" -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -eq 200) {
        Write-Host "      OK: servicio respondiendo en puerto $PORT" -ForegroundColor Green
    }
} catch {
    Write-Host "      AVISO: el servicio puede tardar unos segundos más en estar listo" -ForegroundColor Yellow
}

# IP local
$ip = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Ethernet*","Wi-Fi*" -ErrorAction SilentlyContinue |
       Where-Object { $_.IPAddress -notlike "169.*" -and $_.IPAddress -ne "127.0.0.1" } |
       Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  Instalación completada" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  URL para el equipo:" -ForegroundColor Cyan
if ($ip) {
    Write-Host "      http://${ip}:$PORT"
} else {
    Write-Host "      http://<IP-DE-ESTE-SERVIDOR>:$PORT"
}
Write-Host ""
Write-Host "  Contraseña actual: $PASSWORD" -ForegroundColor Yellow
Write-Host "  (cámbiala editando install_server.ps1 y reejecutando)"
Write-Host ""
Write-Host "  El servicio arrancará automáticamente al encender el servidor."
Write-Host "  Para reiniciarlo manualmente:"
Write-Host "      Stop-ScheduledTask -TaskName $TASK_NAME"
Write-Host "      Start-ScheduledTask -TaskName $TASK_NAME"
Write-Host ""
