# Implica Anonimizador

Herramienta de anonimización de documentos M&A (sumas y saldos, teasers, IMs, datapacks de due diligence) para uso interno en Implica Corporate Finance.

Reemplaza nombres de empresas, personas, CIFs, IBANs, direcciones y datos identificadores por codenames de proyecto. Para libros contables españoles usa códigos PGC (430xxx clientes, 410xxx proveedores, etc.) y mantiene la trazabilidad a través del número de cuenta.

## Modo de uso

### En local (recomendado para datos reales)

```powershell
# Instalación una vez
git clone <este-repo>
cd implica-anonimizador
pip install -r requirements.txt
pip install -e .

# Arrancar UI
streamlit run streamlit_app.py
# o doble-clic en lanzar_anonimizador.bat
```

Abre `http://localhost:8501`. Los archivos nunca salen de tu máquina.

### Demo pública (solo fixtures sintéticos)

Esta app está desplegada en Streamlit Cloud como demo. **No subas datos reales de clientes** — la app está alojada en infraestructura de terceros. Para producción interna, el equipo Implica la usa en un servidor local con `install_server.ps1`.

## Características

- **Auto-detección de tipo de documento**: Excel contable, teaser PPT, contrato legal, documento general
- **Detector PGC para sumas y saldos**: 100% cobertura en cuentas 4xxx/5xx, sin depender de NER
- **Codenames por cuenta**: `[Cliente-4300000125]` con trazabilidad perfecta
- **Multi-formato**: Excel (.xlsx/.xlsm), Word (.docx), PowerPoint (.pptx), PDF
- **Variantes inteligentes**: agrupa "Global Menta S.L.", "GlobalMenta", "Global Menta" como una sola entidad
- **Rehydrate**: revierte codenames a nombres reales después del análisis con Claude

## Documentación

- [`USER_GUIDE.md`](USER_GUIDE.md) — Para usuarios finales
- [`INSTALL.md`](INSTALL.md) — Para IT, despliegue en servidor interno
- [`DEMO.md`](DEMO.md) / [`DEMO_VIDEO.md`](DEMO_VIDEO.md) — Guion de demostración
- [`mensaje_equipo.md`](mensaje_equipo.md) — Plantillas de comunicación

## Confidencialidad

- 100% local en modo producción — los archivos nunca salen del servidor interno de Implica
- Los mappings (`projects/<codename>.json`) están en `.gitignore` y nunca se commitean
- Solo se procesa con NLP local (spaCy en español) — sin llamadas a APIs externas
- El modo demo público (Streamlit Cloud) es solo para fixtures sintéticos

## Stack

Python 3.11+, Streamlit, spaCy (`es_core_news_md`), openpyxl, python-docx, python-pptx, PyMuPDF, rapidfuzz.
