# Guía de instalación — servidor interno

Esta guía es **para la persona que va a instalar el anonimizador en el servidor de oficina** (IT o quien suela montar herramientas internas tipo n8n).

## Requisitos del servidor

- Windows 10/11 o Windows Server
- Python 3.11 o superior (https://www.python.org/downloads/, marcar "Add to PATH")
- Conexión a Internet (solo para la instalación inicial — descargar dependencias y modelo de NLP)
- ~600 MB de espacio en disco
- Permisos de administrador para ejecutar el instalador

> **Sin internet en producción**: una vez instalado, el servidor funciona 100% offline. Los documentos nunca salen de él.

## Instalación en 4 pasos

### 1. Copiar la carpeta al servidor

Copia esta carpeta completa al servidor (por ejemplo a `C:\Apps\implica-anonimizador\`).

### 2. (Opcional) Cambiar la contraseña

Edita `install_server.ps1` y cambia la línea:

```powershell
$PASSWORD = "implica2026"   # cambiar antes de instalar
```

Pon una contraseña fuerte. Esta será la que use el equipo para entrar a la URL.

### 3. Ejecutar el instalador

Clic derecho sobre `install_server.ps1` → **"Ejecutar con PowerShell"**.

Si pide permisos, dile que sí. El instalador:

1. Verifica que Python está disponible.
2. Crea un entorno virtual aislado en `.venv\`.
3. Instala todas las dependencias.
4. Descarga el modelo de NLP en español (~40 MB).
5. Abre el puerto 8501 en el firewall (solo red local, no internet).
6. Crea una tarea programada para arrancar el servicio al boot.
7. Arranca el servicio.

Tarda 2–5 minutos. Al final muestra la URL para el equipo:

```
URL para el equipo:
    http://192.168.X.Y:8501
```

### 4. Repartir la URL y la contraseña

Manda esa URL y la contraseña al equipo. La plantilla del mensaje está en [`mensaje_equipo.md`](mensaje_equipo.md).

## Gestión

### Reiniciar el servicio

```powershell
Stop-ScheduledTask  -TaskName ImplicaAnonimizador
Start-ScheduledTask -TaskName ImplicaAnonimizador
```

### Ver el estado

```powershell
Get-ScheduledTask -TaskName ImplicaAnonimizador | Get-ScheduledTaskInfo
```

### Actualizar a una nueva versión

1. Para el servicio: `Stop-ScheduledTask -TaskName ImplicaAnonimizador`
2. Reemplaza los archivos del proyecto (mantén `projects/` y `.venv/`)
3. Actualiza dependencias: `.\.venv\Scripts\pip install -e .`
4. Vuelve a arrancar: `Start-ScheduledTask -TaskName ImplicaAnonimizador`

### Cambiar contraseña sin reinstalar

Edita `start_server.ps1` (generado por el instalador) y cambia la línea:

```powershell
$env:IMPLICA_ANON_PASSWORD = 'nueva-contraseña'
```

Luego reinicia la tarea.

### Logs

Streamlit imprime a la consola de la tarea. Para verlos en directo:

```powershell
Get-ScheduledTask -TaskName ImplicaAnonimizador | Stop-ScheduledTask
.\start_server.ps1   # ejecutar manualmente para ver logs
```

### Desinstalar

```powershell
.\uninstall_server.ps1
```

Esto quita la tarea y la regla de firewall. **No borra** la carpeta del proyecto ni los mappings en `projects/` por seguridad (contienen los codenames usados en deals reales).

## Seguridad

- El servicio escucha en `0.0.0.0:8501`, accesible desde la red local.
- El firewall permite el puerto solo en perfiles **Domain** y **Private** (no en Public). Si el servidor cambia a red pública, queda automáticamente protegido.
- La contraseña se compara con SHA-256 en memoria; no se loguea.
- Los documentos subidos se procesan en `%TEMP%\` y se borran al cerrar la sesión.
- Los mappings en `projects/*.json` contienen nombres reales de clientes — **no compartir la carpeta `projects/`** fuera del servidor.

## Resolución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Python no encontrado` al instalar | No está en PATH | Reinstala Python marcando "Add to PATH" |
| El equipo no puede acceder a la URL | Firewall del servidor o el cliente | Verifica `Get-NetFirewallRule -DisplayName ImplicaAnonimizador-8501` |
| Pide contraseña en bucle | Está usando la contraseña del instalador antiguo | Verifica `$env:IMPLICA_ANON_PASSWORD` en `start_server.ps1` |
| Procesando archivo grande se queda colgado | Falta de RAM (spaCy carga ~500MB) | Sube la RAM del servidor a 4GB+ |
| Tarda mucho la primera detección | spaCy se carga la primera vez tras el arranque | Normal, las siguientes son instantáneas |
