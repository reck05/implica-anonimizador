# deploy_azure.ps1
# Despliega el Implica Anonimizador en Azure App Service (Linux, contenedor).
#
# REQUISITOS:
#   1. Azure CLI instalado (ya lo tienes).
#   2. Haber hecho `az login` con la cuenta CORRECTA (ver AZURE_DEPLOY.md).
#   3. Docker NO es necesario: Azure construye la imagen desde el Dockerfile (ACR build).
#
# USO:
#   1. Edita las variables de abajo (sobre todo $LOCATION y $APP_NAME).
#   2. Ejecuta:  .\deploy_azure.ps1
#
# Lo que hace: crea resource group + Azure Container Registry + App Service Plan +
# Web App con el contenedor, y configura la contraseña. Luego te recuerda activar
# Easy Auth (login corporativo) — ver AZURE_DEPLOY.md.

# ------------------- CONFIGURACIÓN (edita esto) -------------------
$RESOURCE_GROUP = "rg-implica-anonimizador"
$LOCATION       = "spaincentral"          # region EU/España. Alternativas: westeurope, francecentral
$ACR_NAME       = "acrimplicaanon$((Get-Random -Maximum 99999))"  # debe ser único global, solo minúsculas/números
$PLAN_NAME      = "plan-implica-anon"
$APP_NAME       = "implica-anonimizador"  # parte de la URL: https://<APP_NAME>.azurewebsites.net (debe ser único)
$SKU            = "B1"                      # B1 ~13€/mes. Para producción real considera P1v3.
$PASSWORD       = "CAMBIA-ESTA-CONTRASEÑA"  # contraseña de la app (segunda capa; la principal es Easy Auth)
$IMAGE_TAG      = "implica-anon:latest"
# ------------------------------------------------------------------

$ErrorActionPreference = "Stop"
Write-Host "== Implica Anonimizador -> Azure App Service ==" -ForegroundColor Cyan

# 0) Verificar login
$acct = az account show --query name -o tsv 2>$null
if (-not $acct) { Write-Host "Haz 'az login' primero." -ForegroundColor Red; exit 1 }
Write-Host "Suscripción activa: $acct"

# 1) Resource group
Write-Host "[1/6] Resource group en $LOCATION..." -ForegroundColor Yellow
az group create --name $RESOURCE_GROUP --location $LOCATION | Out-Null

# 2) Azure Container Registry
Write-Host "[2/6] Container Registry $ACR_NAME..." -ForegroundColor Yellow
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic --admin-enabled true | Out-Null

# 3) Construir la imagen EN Azure (no necesitas Docker local)
Write-Host "[3/6] Construyendo imagen en ACR (tarda unos minutos)..." -ForegroundColor Yellow
az acr build --registry $ACR_NAME --image $IMAGE_TAG .

# 4) App Service Plan (Linux)
Write-Host "[4/6] App Service Plan ($SKU)..." -ForegroundColor Yellow
az appservice plan create --name $PLAN_NAME --resource-group $RESOURCE_GROUP --is-linux --sku $SKU | Out-Null

# 5) Web App con el contenedor
Write-Host "[5/6] Web App $APP_NAME..." -ForegroundColor Yellow
$ACR_SERVER = az acr show --name $ACR_NAME --query loginServer -o tsv
az webapp create --resource-group $RESOURCE_GROUP --plan $PLAN_NAME --name $APP_NAME `
    --deployment-container-image-name "$ACR_SERVER/$IMAGE_TAG" | Out-Null

# Credenciales del ACR para que la Web App pueda tirar de la imagen
$ACR_USER = az acr credential show --name $ACR_NAME --query username -o tsv
$ACR_PASS = az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv
az webapp config container set --name $APP_NAME --resource-group $RESOURCE_GROUP `
    --docker-custom-image-name "$ACR_SERVER/$IMAGE_TAG" `
    --docker-registry-server-url "https://$ACR_SERVER" `
    --docker-registry-server-user $ACR_USER `
    --docker-registry-server-password $ACR_PASS | Out-Null

# 6) Configuración de la app
Write-Host "[6/6] Configurando puerto y contraseña..." -ForegroundColor Yellow
az webapp config appsettings set --name $APP_NAME --resource-group $RESOURCE_GROUP --settings `
    WEBSITES_PORT=8501 `
    IMPLICA_ANON_PASSWORD="$PASSWORD" `
    WEBSITES_CONTAINER_START_TIME_LIMIT=600 | Out-Null

$URL = "https://$APP_NAME.azurewebsites.net"
Write-Host ""
Write-Host "== Despliegue lanzado ==" -ForegroundColor Green
Write-Host "  URL: $URL"
Write-Host "  (el primer arranque tarda 3-5 min mientras descarga el contenedor)"
Write-Host ""
Write-Host "SIGUIENTE PASO CRÍTICO DE SEGURIDAD:" -ForegroundColor Yellow
Write-Host "  Activa 'Authentication' (Easy Auth) con Microsoft Entra ID en el portal"
Write-Host "  para que solo el equipo de Implica pueda entrar. Ver AZURE_DEPLOY.md."
