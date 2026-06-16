# Capa opcional GLiNER

GLiNER es un detector de entidades por *prompting* de etiquetas: le dices qué
quieres ("EMPRESA_OBJETIVO", "FONDO", "DESPACHO_LEGAL"...) y las detecta sin
reentrenar. Aquí es una **capa opcional** que **complementa** —no sustituye— a
spaCy + regex + heurísticas + PGC.

## Confidencialidad / coste (garantías)

- Es la **librería local de Python** (`GLiNER.from_pretrained` + `predict_entities`).
  **NO** es una API de pago, **NO** es un servicio hosted, **NO** usa "Inference
  Provider", endpoint remoto ni token de HuggingFace.
- La **inferencia es 100% local**: nunca se envían documentos, texto, entidades ni
  fragmentos a HuggingFace, OpenAI, Claude, Google, Azure AI ni a ningún servicio.
- Coste **0 € de servicio**: solo coste de tu máquina/servidor.
- La **descarga del modelo** desde HuggingFace es **opcional y explícita**
  (`IMPLICA_GLINER_ALLOW_DOWNLOAD=true`). Por defecto está **prohibida**: si el modelo
  no está en caché local, la app fuerza modo offline y cae al motor clásico.

## Estado por defecto: DESACTIVADA y sin descargas

Sin configurar nada: la app funciona igual que siempre (spaCy + regex + heurísticas
+ PGC). GLiNER no se carga, no se importa y **no descarga nada**.

## Licencia (IMPORTANTE para uso comercial)

| Componente | Licencia |
|---|---|
| Librería GLiNER | Apache-2.0 (uso comercial OK) |
| **Modelo por defecto** `gliner-community/gliner_medium-v2.1` | Apache-2.0 (org. que re-publica para uso comercial), multilingüe |
| `knowledgator/*` | Apache-2.0 (comercial OK), pero suelen ser **solo inglés** |
| `urchade/gliner_multi-*` | ⚠️ Suelen ser **CC-BY-NC-4.0 (NO comercial)** → **EVITAR** |

> ⚠️ **Antes de uso comercial, verifica la licencia exacta en la model card de
> HuggingFace del modelo que vayas a usar.** La licencia de la librería NO es la del
> modelo. Implica es un despacho comercial → usa solo modelos con licencia que permita
> uso comercial (Apache-2.0 / MIT).

## Descargar el modelo UNA vez (paso manual y explícito)

En una máquina con internet, una sola vez:

```powershell
pip install -r requirements-gliner.txt

# Opción A: comando del proyecto (descarga a la caché local de HuggingFace)
python -m implica_anon.gliner_detector

# Opción B: descarga directa (sin token, modelo público)
huggingface-cli download gliner-community/gliner_medium-v2.1
```

Tras esto el modelo queda en `~/.cache/huggingface`. A partir de ahí funciona
**offline** y `IMPLICA_GLINER_ALLOW_DOWNLOAD` puede quedarse en `false`.

> En un servidor sin internet (air-gapped): descarga en otra máquina y copia la
> carpeta de caché del modelo al servidor.

## Activar (una vez descargado el modelo)

```powershell
$env:IMPLICA_ENABLE_GLINER = "true"
# IMPLICA_GLINER_ALLOW_DOWNLOAD se queda en false (ya está descargado)
streamlit run streamlit_app.py
```

Ajustes opcionales:
```powershell
$env:IMPLICA_GLINER_THRESHOLD = "0.5"                              # confianza [0..1]
$env:IMPLICA_GLINER_MODEL     = "gliner-community/gliner_medium-v2.1"
$env:IMPLICA_GLINER_LABELS    = "EMPRESA,FONDO,PERSONA"            # override etiquetas
```

## Comportamiento si NO está disponible

- `gliner` no instalado, o modelo no en caché y descarga prohibida →
  la app muestra **"GLiNER no disponible, usando motor clásico"** y sigue con
  spaCy + regex + heurísticas. **Nunca rompe ni descarga nada.**

## Desactivar

```powershell
Remove-Item Env:\IMPLICA_ENABLE_GLINER
```

## Qué detecta (etiquetas M&A)

PERSONA, EMPRESA, EMPRESA_OBJETIVO, COMPRADOR, VENDEDOR, FONDO, BANCO, ASESOR_MA,
DESPACHO_LEGAL, AUDITOR, ACCIONISTA, CEO, CFO, FOUNDER, PROJECT_NAME, DEAL_NAME,
MARCA, GRUPO_EMPRESARIAL, DOMINIO_WEB.

La etiqueta fina se conserva en `Candidate.source` (p.ej. `gliner:FONDO`); para el
reemplazo se mapea a kinds del pipeline (ORG/PER/BANCO/GRUPO/DOMINIO).

**No anonimiza importes, revenue, EBITDA, deuda ni múltiplos** (no están entre las etiquetas).

## Garantías de diseño

- No sustituye el motor PGC: GLiNER solo actúa en la ruta NER (texto libre).
- No cambia el flujo: solo añade candidatos, deduplicados contra los ya detectados.
- El humano revisa y confirma en la tabla; el reemplazo es determinista + verify pass.
- Logs sin texto sensible: solo conteos y tipos de error.

## Tests

```powershell
python tests/test_gliner.py
```

Mockean la salida del modelo (no requieren gliner instalado). Cubren: activación,
mapeo de etiquetas, dedup, fallback, descarga deshabilitada por defecto y mensaje de
motor clásico. El test del modelo real se salta si `gliner` no está instalado.

## Producción (Azure)

La imagen Docker NO incluye GLiNER y `IMPLICA_GLINER_ALLOW_DOWNLOAD` está en false →
en Azure sigue desactivado y sin descargas. Habilitarlo sería una decisión consciente
(añadir gliner a la imagen + descargar el modelo en build + poner las env vars).
