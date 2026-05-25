# Guía rápida de uso — Implica Anonimizador

> Herramienta para anonimizar documentos M&A (teasers, datapacks, memos) reemplazando nombres de empresas y datos identificadores por codenames de proyecto.

## Acceso

1. Abre tu navegador (Chrome, Edge, Firefox).
2. Ve a la URL que te ha pasado IT (algo como `http://192.168.X.Y:8501`).
3. Introduce la contraseña.

> Solo funciona estando conectado a la red de la oficina (o VPN).

## Cómo anonimizar un deal nuevo

### Paso 1 — Codename del proyecto

En la barra lateral izquierda:

- **Modo**: "Nuevo proyecto"
- **Codename del proyecto**: el nombre interno del deal (ej. `paradise`, `eden`, `atlas`)

> Este será el codename por defecto para la empresa principal del deal. Las personas, NIF, IBAN, etc. tendrán placeholders genéricos.

### Paso 2 — Subir los archivos

Arrastra los archivos a la zona central (o pulsa "Browse files"). Puedes subir varios a la vez:

- Excel (`.xlsx`, `.xlsm`)
- Word (`.docx`)
- PowerPoint (`.pptx`)
- PDF (`.pdf`) — siempre que sea PDF con texto seleccionable, no escaneado

### Paso 3 — Detectar

Pulsa **🔍 Detectar candidatos**.

El sistema lee todos los archivos y detecta:

- **Empresas** (con sus variantes: "Global Menta S.L.", "GlobalMenta", "Global Menta")
- **Personas** (nombres propios)
- **CIF, NIF, IBAN, emails, teléfonos, direcciones**

> La primera detección tarda ~30 segundos. Las siguientes son inmediatas.

### Paso 4 — Revisar la tabla

Aparece una tabla con todos los candidatos. Cada fila tiene:

| Columna | Qué hacer |
|---|---|
| **Anonimizar** | Desmárcalo si es un falso positivo (ej. detectó "Compañía" como empresa). |
| **Tipo** | Solo informativo. |
| **Canónico** | La forma más completa del nombre detectado. |
| **Variantes detectadas** | Otras formas que aparecen en el documento. Todas se reemplazarán por el mismo codename. |
| **Ocurrencias** | Cuántas veces aparece en total. |
| **Codename →** | Edítalo. Por defecto sugiere algo razonable: el codename del proyecto para la empresa principal, `[CEO]`, `[Persona-1]`, `[CIF-1]`, etc. para el resto. |

### Paso 5 — Anonimizar

Pulsa **✅ Anonimizar y descargar**.

Recibes un ZIP con todos los archivos procesados. Los originales quedan intactos.

## Cómo procesar más archivos del mismo deal

Cuando vuelves a abrir la herramienta y eliges **"Continuar proyecto existente"** → tu proyecto, los codenames ya guardados aparecen pre-rellenados. Solo te preguntará por entidades nuevas que no estaban antes.

> Útil para datapacks que llegan en oleadas: el primer Excel define los codenames, los siguientes los reutilizan automáticamente.

## Qué se preserva en los archivos

- **Excel**: celdas, fórmulas, formato, nombres de hojas (los reemplaza también).
- **Word**: párrafos, tablas, headers/footers, formato de fuente.
- **PowerPoint**: texto en slides, tablas, notas de speaker.
- **PDF**: layout original. El texto reemplazado se superpone sobre el original (similar a una redacción).

## Qué NO se toca

- **Fórmulas de Excel**: las celdas con `=SUMA(...)` no se modifican, son lógica.
- **Imágenes dentro de los documentos**: si un logo aparece como imagen, no se anonimiza. Borra esas imágenes a mano antes.
- **PDFs escaneados**: si el PDF es una foto/escaneo sin texto OCR, no detecta nada. Pasa esos PDFs por Adobe Acrobat > "Reconocer texto" primero.

## Preguntas frecuentes

**¿Y si el documento tiene un nombre raro que no detecta?**
Avísale a IT. Pueden añadirlo manualmente al mapping desde la terminal:
```powershell
implica-anon add-entry paradise "EmpresaRaraSL" Paradise -k ORG
```

**¿Y si me equivoco y quiero cambiar un codename?**
Vuelve a abrir el proyecto, edita el codename en la tabla y vuelve a procesar. El mapping se sobreescribe.

**¿Los archivos quedan guardados en el servidor?**
No. Se procesan en memoria temporal y se borran al cerrar la pestaña. Solo se guarda el `mapping.json` con las correspondencias.

**¿Es seguro subir documentos confidenciales?**
Sí. El servidor está dentro de la red de Implica, no envía nada a internet, y los archivos se procesan localmente.

**¿Y si meto un Excel de 50 hojas y 100.000 filas?**
Funciona pero tarda. Para deals muy grandes, divide el datapack en bloques de ~5 archivos.

## Cuándo NO usar esto

- Si necesitas anonimización **certificada o legal** (GDPR-grade, cumplimiento auditado). Esta herramienta es para uso interno; no es una solución de pseudonimización certificada.
- Si los datos a anonimizar incluyen **información médica o categorías especiales** del RGPD. Esos casos requieren herramientas específicas con trazabilidad.
- Para PDFs escaneados sin OCR previo (no detecta nada).
