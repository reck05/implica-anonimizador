# deploy_azure_containerapps.ps1
# Despliega el Implica Anonimizador en Azure Container Apps (escala a cero, ~0-5€/mes).
#
# REQUISITOS:
#   1. Azure CLI + `az login` con la cuenta corporativa de Implica.
#   2. No necesitas Docker local: Azure construye la imagen desde el Dockerfile.
#
# USO:  .\deploy_azure_containerapps.ps1

# ------------------- CONFIGURACIÓN -------------------
$RESOURCE_GROUP = "rg-implica-anonimizador"
$LOCATION       = "spaincentral"          # región EU. Alternativa garantizada: westeurope
$APP_NAME       = "implica-anonimizador"
$PASSWORD       = "CAMBIA-ESTA-CONTRASEÑA" # 2ª capa; la principal es Easy Auth (Entra ID)
# -----------------------------------------------------

$ErrorActionPreference = "Stop"

# Prerrequisitos (idempotente)
az extension add --name containerapp --upgrade --only-show-errors
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.OperationalInsights --wait

# Build desde Dockerfile + despliegue en un solo comando.
# Crea solo: ACR, Container Apps Environment y la app. Escala a cero por defecto.
az containerapp up `
    --name $APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --location $LOCATION `
    --source . `
    --ingress external `
    --target-port 8501 `
    --env-vars IMPLICA_ANON_PASSWORD="$PASSWORD"

# URL resultante
$URL = az containerapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv
Write-Host ""
Write-Host "Desplegado en: https://$URL" -ForegroundColor Green
Write-Host ""
Write-Host "SIGUIENTE PASO (seguridad): activa Easy Auth con Microsoft Entra ID" -ForegroundColor Yellow
Write-Host "para que solo el equipo de Implica entre. Ver AZURE_DEPLOY.md."
Write-Host ""
Write-Host "Escala a cero: si nadie la usa, no factura. La 1a visita tras inactividad tarda ~15s."
