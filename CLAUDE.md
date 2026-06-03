# CLAUDE.md

Contexto del proyecto **Implica Anonimizador** para sesiones de Claude Code.
Este archivo lo lee Claude Code automáticamente al abrir la carpeta — no hace falta pegarlo en cada prompt.

## Qué es

Herramienta interna de **Implica Corporate Finance** que anonimiza documentos M&A (sumas y saldos, teasers, IMs, datapacks de due diligence) reemplazando nombres reales por codenames de proyecto. Soporta Excel, Word, PowerPoint y PDF.

**Caso de uso principal:** procesar un sumas y saldos del cliente, anonimizarlo, pasarlo a Claude para análisis QoE/partes vinculadas/DFN, y rehidratar la respuesta para el informe interno — todo sin que ningún nombre real salga de Implica.

## Arquitectura

```
implica-anonimizador/
├── streamlit_app.py             # UI principal: 2 tabs (Anonimizar + Rehydrate)
├── implica_anon/
│   ├── cli.py                   # CLI con typer (`implica-anon run ...`)
│   ├── detectors.py             # NER spaCy + regex (CIF/NIF/IBAN/email/teléfono) + clustering
│   ├── accounting.py            # Detector PGC para libros contables españoles (430xxx clientes, 410xxx proveedores, etc.)
│   ├── doctype.py               # Auto-detección tipo: accounting | teaser_im | legal | generic
│   ├── mapping.py               # Persistencia nombre↔codename en projects/<codename>.json
│   ├── rehydrate.py             # Revertir codenames a nombres reales
│   ├── replacer.py              # Núcleo de reemplazo de texto (case-insensitive, order by length desc)
│   ├── interactive.py           # UI Rich para CLI + labels y placeholders
│   └── formats/
│       ├── excel.py             # openpyxl, data_only=True, filtra fórmulas
│       ├── word.py              # python-docx
│       ├── pptx.py              # python-pptx
│       └── pdf.py               # PyMuPDF (fitz), redact + insert
├── tests/
│   ├── fixtures/                # Excel/PPT sintéticos para tests (NUNCA datos reales)
│   ├── test_round_trip.py       # E2E: anonimiza → rehidrata → verifica
│   ├── test_pgc.py              # Test detector PGC
│   ├── test_realista.py         # Test contra fixture realista (multi-hoja + fórmulas)
│   └── make_*.py                # Generadores de fixtures
├── projects/                    # Mappings por deal (gitignored, contiene PII)
├── .streamlit/config.toml       # Oculta menú deploy, theme Implica
├── lanzar_anonimizador.bat      # Doble-clic para arrancar UI local
├── install_server.ps1           # Instalador en servidor interno (para IT)
└── streamlit_app.py
```

## Confidencialidad — REGLA DE ORO

1. **NUNCA** commitear `projects/*.json` (contienen nombres reales de clientes mapeados a codenames).
2. **NUNCA** commitear archivos `.xlsx/.xlsm/.docx/.pptx/.pdf` excepto los de `tests/fixtures/` (que son sintéticos).
3. Verificar antes de cada commit: `git status` y comprobar que no aparezca nada de `projects/` ni archivos Office reales.
4. **NUNCA** subir datos reales a la versión Streamlit Cloud — solo a la instalación local o servidor interno.
5. La carpeta `C:\Users\Usuario\IMPLICA CF\` contiene datos reales — **jamás copiar archivos de ahí al repo**.

## Flujos clave

### Flujo accounting (sumas y saldos)
1. `accounting.scan_workbook(path)` busca columnas Cuenta/Concepto/Debe/Haber
2. Para cada fila, clasifica por prefijo de cuenta (430xxx → CLIENTE, etc.)
3. `detectors.candidates_from_pgc(scan)` propaga el `account_code` a cada Candidate
4. `cluster_variants(candidates)` agrupa duplicados
5. Codename derivado del código de cuenta: `[Cliente-4300000125]`
6. `formats.apply_replacements(src, mapping, dst)` aplica al Excel

### Flujo NER (teaser/memo/PDF)
1. `formats.extract_text(path)` por formato
2. `detectors.detect_candidates(texts)` con spaCy + regex
3. `cluster_variants` con dedup cross-source (PGC gana sobre NER si coinciden)
4. UI pregunta codenames interactivamente
5. Aplicar

### Flujo rehydrate
1. `rehydrate.invert_mapping(pm)` → `{codename: original}`
2. Aplica con `replace_in_text` (mismo motor que anonimización)

## Convenciones

- **Python 3.11+** (fijado en `.python-version` y `runtime.txt`)
- `from __future__ import annotations` en todos los módulos
- Type hints siempre que se pueda
- Docstrings en **español** (es producto interno español)
- **NO** usar emojis en código a menos que el usuario los pida; **SÍ** se usan en UI (Streamlit) por estética
- Commit messages cortos, en español o inglés, sin emojis ni "Co-Authored-By"
- Tests son scripts directos (`python tests/test_xxx.py`), no pytest formal
- `_funcion_privada` con underscore prefix

## Comandos típicos

```powershell
# Setup
pip install -e .
python -m spacy download es_core_news_md

# Arrancar UI
streamlit run streamlit_app.py
# o doble-clic en lanzar_anonimizador.bat

# CLI
implica-anon run archivo.xlsx -p paradise
implica-anon list
implica-anon show paradise

# Tests
python tests/test_round_trip.py
python tests/test_pgc.py
python tests/test_realista.py

# Generar fixtures sintéticos
python tests/make_sumas_saldos_real.py
python tests/make_pptx_teaser.py
```

## Stack

- **UI:** Streamlit ≥1.31
- **NLP:** spaCy ≥3.7,<4.0 con modelo `es_core_news_md`
- **Excel:** openpyxl
- **Word:** python-docx
- **PowerPoint:** python-pptx
- **PDF:** PyMuPDF (fitz)
- **Fuzzy match:** rapidfuzz
- **CLI:** typer + rich

## Despliegues

| Modo | Cuándo usarlo | Cómo se arranca |
|---|---|---|
| **Local** (recomendado producción) | Datos reales del cliente | `lanzar_anonimizador.bat` o `streamlit run` |
| **Servidor interno Implica** | Equipo entero (10+ usuarios) | IT ejecuta `install_server.ps1` en PC fijo |
| **Streamlit Cloud (demo)** | Enseñar a stakeholders | Solo fixtures sintéticos, no datos reales |

## Issues conocidos / Limitaciones

- PDFs escaneados sin OCR no se detectan (necesitan preprocesado con Tesseract).
- Excel con muchas fórmulas SUMIFS multi-hoja: si Excel no cacheó valores, openpyxl lee la fórmula cruda (`data_only=True` falla). Mitigado en `formats/excel.py` con filtro `_looks_like_formula_or_ref`.
- spaCy con nombres "raros" (comerciales sin formato típico): el detector PGC lo mitiga al usar el código de cuenta como autoridad.
- En Streamlit Cloud el primer análisis tarda ~60s porque descarga el modelo (~40MB) al vuelo.

## Quién usa esto y para qué

- **Analistas de Implica CF** anonimizan datapacks de due diligence antes de pasarlos a Claude o a un comprador en VDR.
- **Asociados/socios** usan los outputs anonimizados para reports internos sin filtrar PII.
- **IT** despliega y mantiene la versión interna.

## Quién NO debe modificar qué

- `accounting.PGC_PREFIXES` — solo si cambia el PGC español oficial (raro). Si añades, verifica con un contable.
- `.gitignore` — mantén las reglas de archivos Office y `projects/*.json`. **Nunca relajar**.
- `streamlit_app.py:_check_password` — auth simple. No cambiar sin coordinar con IT.
