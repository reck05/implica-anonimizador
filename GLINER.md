# Capa opcional GLiNER

GLiNER es un detector de entidades por *prompting* de etiquetas: le dices qué
quieres ("EMPRESA_OBJETIVO", "FONDO", "DESPACHO_LEGAL"...) y las detecta sin
reentrenar. Aquí es una **capa opcional** que **complementa** —no sustituye— a
spaCy + regex + heurísticas + PGC.

## Estado por defecto: DESACTIVADA

Sin configurar nada, la app funciona exactamente igual que antes (spaCy + regex +
heurísticas + PGC). GLiNER no se carga ni se importa.

## Activar

```powershell
# 1) Instalar las dependencias opcionales (arrastra torch; primer uso descarga el modelo ~500MB-1GB)
pip install -r requirements-gliner.txt

# 2) Activar por variable de entorno
$env:IMPLICA_ENABLE_GLINER = "true"

# (opcional) ajustes
$env:IMPLICA_GLINER_THRESHOLD = "0.5"                       # confianza mínima [0..1]
$env:IMPLICA_GLINER_MODEL     = "urchade/gliner_multi-2.1"  # modelo HuggingFace
$env:IMPLICA_GLINER_LABELS    = "EMPRESA,FONDO,PERSONA"     # override de etiquetas M&A

# 3) Arrancar normal
streamlit run streamlit_app.py
```

## Desactivar

```powershell
Remove-Item Env:\IMPLICA_ENABLE_GLINER   # o ponerlo a "false"
```

O simplemente no instalar `gliner`: aunque la variable esté a `true`, si el paquete
no está, la app cae a spaCy+regex+heurísticas sin error.

## Qué detecta (etiquetas M&A)

PERSONA, EMPRESA, EMPRESA_OBJETIVO, COMPRADOR, VENDEDOR, FONDO, BANCO, ASESOR_MA,
DESPACHO_LEGAL, AUDITOR, ACCIONISTA, CEO, CFO, FOUNDER, PROJECT_NAME, DEAL_NAME,
MARCA, GRUPO_EMPRESARIAL, DOMINIO_WEB.

La etiqueta fina se conserva (en `Candidate.source`, p.ej. `gliner:FONDO`); para el
reemplazo se mapea a los kinds del pipeline (ORG/PER/BANCO/GRUPO/DOMINIO).

**No anonimiza importes, revenue, EBITDA, deuda ni múltiplos.** Esas no están entre
las etiquetas.

## Garantías de diseño

- 100% local: el modelo se descarga una vez de HuggingFace y luego corre offline.
  No se envía texto del documento a ningún servicio externo.
- No sustituye el motor PGC: GLiNER solo actúa en la ruta NER (texto libre).
- No cambia el flujo: solo añade candidatos, deduplicados contra los ya detectados.
- El humano sigue revisando y confirmando en la tabla; el reemplazo es determinista
  y pasa por el verify pass anti-fuga.
- Logs sin texto sensible: solo conteos y tipos de error.

## Tests

```powershell
python tests/test_gliner.py
```

Los tests mockean la salida del modelo (no requieren gliner instalado). El test del
modelo real se ejecuta solo si `gliner` está instalado; si no, se salta.

## Producción (Azure)

La imagen Docker NO incluye GLiNER → en Azure sigue desactivado. Para habilitarlo en
producción habría que añadir `gliner` a la imagen y poner `IMPLICA_ENABLE_GLINER=true`
como app setting — decisión consciente, no por defecto.
