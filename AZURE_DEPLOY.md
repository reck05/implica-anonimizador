# Desplegar en Azure — guía

Despliega el anonimizador como **Azure App Service (Linux, contenedor)**.

## ⚠️ Antes de nada: confidencialidad

| Cuenta Azure | ¿Datos reales de cliente? |
|---|---|
| **Tenant corporativo de Implica** (mismo login que OneDrive), región EU, acceso restringido | ✅ Sí, es infraestructura controlada por el despacho |
| **Cuenta personal** (tu tarjeta) | ❌ Solo demo con fixtures sintéticos — nunca datapacks reales |

Desplegar la app (crear los recursos) es seguro: la app arranca **vacía**, los datos de cliente solo entran cuando alguien sube un archivo. Lo que importa es: **región EU + acceso restringido (Easy Auth) + cuenta corporativa** antes de procesar nada real.

## Paso 1 — Autenticar la CLI de Azure

El login del navegador NO basta; la CLI necesita su propia sesión. En una terminal PowerShell:

```powershell
az login
```

Se abre el navegador (donde ya estás logueado) → confirmas → la CLI queda autenticada.

Verifica a qué cuenta entraste:

```powershell
az account show --query "{suscripcion:name, tenant:tenantId, usuario:user.name}" -o table
```

- Si el `usuario` es tu email `@implicacf.com` y la suscripción es de la empresa → tenant corporativo ✅
- Si es una cuenta personal (gmail, hotmail, pay-as-you-go propio) → solo demo ⚠️

Si tienes varias suscripciones, elige la corporativa:
```powershell
az account list -o table
az account set --subscription "<nombre-o-id-de-la-suscripcion-de-Implica>"
```

## Paso 2 — Desplegar

Edita `deploy_azure.ps1` (sobre todo `$LOCATION`, `$APP_NAME` y `$PASSWORD`) y ejecútalo:

```powershell
.\deploy_azure.ps1
```

Crea: resource group + Container Registry + App Service Plan + Web App, construye la imagen en Azure (no necesitas Docker local) y arranca la app. Tarda ~5-10 min. Al final te da la URL `https://<APP_NAME>.azurewebsites.net`.

## Paso 3 — CRÍTICO: restringir el acceso (Easy Auth)

Por defecto la URL es pública. Para que **solo el equipo de Implica** entre, activa la autenticación corporativa (no requiere código):

1. Portal de Azure → tu Web App → **Authentication** (menú izquierdo)
2. **Add identity provider** → **Microsoft** (Entra ID)
3. Deja los valores por defecto (crea la app registration sola)
4. **Restrict access**: "Require authentication"
5. **Unauthenticated requests**: "HTTP 302 redirect to log in"
6. Guardar

Ahora cualquiera que abra la URL tiene que loguearse con su cuenta de Implica. La contraseña de `IMPLICA_ANON_PASSWORD` queda como segunda capa (puedes quitarla si Easy Auth basta).

> Opcional adicional: **Networking → Access restrictions** para permitir solo IPs de la oficina/VPN.

## Paso 4 — Verificar

Abre la URL, loguéate, sube `tests/fixtures/sumas_saldos_realista.xlsx`, comprueba que anonimiza. Solo cuando Easy Auth esté activo y la cuenta sea corporativa → ya puedes procesar datapacks reales.

## Costes orientativos

| Recurso | SKU | Coste aprox. |
|---|---|---|
| App Service Plan | B1 | ~13 €/mes |
| Container Registry | Basic | ~5 €/mes |
| **Total** | | **~18 €/mes** |

Para producción con más uso: P1v3 (~110 €/mes). Para apagar y no pagar: `az group delete --name rg-implica-anonimizador`.

## Gestión

```powershell
# Ver logs en vivo
az webapp log tail --name <APP_NAME> --resource-group rg-implica-anonimizador

# Redesplegar tras cambios (reconstruye imagen y reinicia)
az acr build --registry <ACR_NAME> --image implica-anon:latest .
az webapp restart --name <APP_NAME> --resource-group rg-implica-anonimizador

# Cambiar la contraseña
az webapp config appsettings set --name <APP_NAME> --resource-group rg-implica-anonimizador --settings IMPLICA_ANON_PASSWORD="nueva"

# Borrar todo (deja de facturar)
az group delete --name rg-implica-anonimizador --yes
```

## Alternativa: Azure Container Apps

Si prefieres escala-a-cero (paga solo por uso, $0 cuando nadie lo usa) en vez de App Service, se puede usar Container Apps. Dímelo y preparo el script equivalente. App Service es más simple para el Easy Auth corporativo, por eso es el camino por defecto.
