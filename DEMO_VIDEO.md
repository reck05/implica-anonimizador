# Cómo grabar la demo en video (5 minutos)

> Para enviar por email/Slack a tu jefe. Tu jefe lo ve cuando quiera, sin instalación, sin links que caduquen.

## Herramienta recomendada

**Loom** (https://loom.com) — gratis, sube y comparte con un link.

- Cuenta gratis: vídeos de hasta 5 min, hasta 25 vídeos
- Instalas la extensión Chrome o app desktop (~1 min)
- Click en grabar → pantalla + cámara opcional → para → te da link tipo `https://loom.com/share/xxx`
- Lo mandas por email o Slack, tu jefe lo abre desde cualquier dispositivo

**Alternativa sin instalar nada**: Win+G (Windows Game Bar) graba pantalla → archivo MP4 → lo subes a Drive/OneDrive y mandas link.

## Preparación (3 minutos antes de grabar)

Ten 3 cosas abiertas en tu pantalla:

1. **Navegador en `http://localhost:8501`** (Streamlit corriendo). Verifica que ves la UI completa.
2. **Explorador de Windows** en `C:\Users\Usuario\implica-anonimizador\tests\fixtures\` (donde está `sumas_saldos_realista.xlsx`).
3. **Claude.ai abierto** en otra pestaña, logueado.

Cierra todo lo demás (Slack, email, WhatsApp). No quieres que aparezcan notificaciones en mitad del vídeo.

## Script segundo a segundo

### 0:00 – 0:30 — Introducción (presenta el problema)

> *"Hola [nombre del jefe]. Te grabo este vídeo de 5 minutos para enseñarte el anonimizador de documentos que llevo unas semanas montando. Lo necesitamos para usar Claude e IA en general con datapacks de clientes sin romper confidencialidad. Te enseño cómo funciona con un ejemplo real."*

En pantalla: ventana de Streamlit (`localhost:8501`).

### 0:30 – 1:00 — Lo que hace (resumen)

> *"En 5 segundos coge un sumas y saldos, identifica automáticamente los clientes (cuentas 430xxx), proveedores (410xxx), bancos, personas, CIFs e IBANs, y los reemplaza por codenames que mantienen la trazabilidad pero no revelan nombres. Cero envío a internet — todo se procesa local."*

En pantalla: enseña el sidebar con "Codename del proyecto" → escribe `paradise`.

### 1:00 – 2:30 — La demo en vivo: anonimizar

1. **Arrastra** `sumas_saldos_realista.xlsx` al área de upload.
2. Comenta: *"Este es un sumas y saldos sintético con la misma estructura que los reales — múltiples hojas mensuales, fórmulas SUMIFS, 30 entidades a anonimizar entre clientes, proveedores, personas, bancos."*
3. Pulsa **🔍 Analizar**.
4. Mientras procesa: *"Detecta automáticamente que es un libro contable. No usa IA para esto, usa el Plan General Contable — es determinista, no falla."*
5. Cuando aparezca la tabla, enseña:
   - *"Mira la columna **Variantes**: detectó que 'CAIXABANK' y 'CAIXABANK, SA' son la misma entidad, los agrupa."*
   - *"Y los codenames son los **códigos de cuenta**: `[Cliente-4300000125]`. Así si Claude me dice algo sobre el Cliente-4300000125, yo busco esa cuenta exacta en mi sumas y saldos original."*
6. Pulsa **✅ Anonimizar y descargar**.

### 2:30 – 3:30 — Enseñar el archivo anonimizado

1. Abre el ZIP descargado → abre el `.xlsx` anonimizado.
2. Comenta:
   - *"Importes intactos."*
   - *"Fórmulas funcionando — los totales se siguen calculando bien."*
   - *"Nombres reemplazados. No queda ni un nombre real."*
3. Comenta el output: *"Esto es lo que le pasaría a Claude o, si fuera necesario, a un comprador en un VDR."*

### 3:30 – 4:30 — Análisis con Claude

1. Cambia a la pestaña de Claude.
2. Sube el archivo anonimizado.
3. Escribe un prompt: *"Analiza este sumas y saldos. Identifica los top 5 clientes por saldo y posibles partes vinculadas."*
4. Mientras Claude responde, comenta: *"Claude ve `[Cliente-4300000003]` en lugar de la empresa real, pero puede razonar perfectamente sobre saldos, concentración, ratios."*
5. Cuando responda, **copia un trozo de la respuesta**.

### 4:30 – 5:00 — Rehidratar y cierre

1. Vuelve a Streamlit → tab **↩️ Rehydrate** → modo "Texto pegado".
2. Pega la respuesta de Claude, pulsa rehidratar.
3. Enseña el resultado: *"Aquí están los nombres reales para mi informe interno. Esto SÍ contiene PII, así que se queda dentro de Implica."*
4. Cierre:

> *"Tres puntos importantes: uno, todo el procesado es local — cumple con confidencialidad. Dos, para que el equipo lo use, IT lo monta en un servidor interno en 10 minutos, igual que hicimos con n8n. Tres, está listo para probar con un deal real cuando quieras. Si te parece bien lo siguiente sería darle acceso al equipo. Dime qué te parece."*

## Después de mandar el video

Cuando tu jefe te conteste:

### Si dice "OK, hagamos esto"

Pásale `INSTALL.md` a IT junto con la carpeta completa. En 10 minutos tienes URL para el equipo.

### Si pide ver más detalles o tiene dudas

**Plan B — Demo en vivo por videollamada**:

1. Convocas un Meet/Teams de 15 min.
2. Compartes pantalla.
3. Sigues el mismo guion pero en vivo, contestando preguntas.
4. **Cero exposición a internet** — solo se ve tu pantalla por la videollamada cifrada de Teams/Meet.

### Si quiere probarlo él mismo en su portátil

Le mandas la carpeta `C:\Users\Usuario\implica-anonimizador\` por OneDrive interno + `USER_GUIDE.md`. La instala con `lanzar_anonimizador.bat`.

## Detalles técnicos para no fallar

- **Resolución**: graba en 1080p mínimo. La tabla de candidatos tiene texto pequeño.
- **Audio**: usa los auriculares con micro, no el micro del portátil — se nota mucho la diferencia.
- **Cierra notificaciones**: modo "no molestar" de Windows (Win+A → Concentración).
- **Sin ensayar suena natural**, pero practica una vez los 5 actos antes de grabar — pillarás cosas raras de la UI.
- **No grabes nada confidencial**: usa el fixture sintético `sumas_saldos_realista.xlsx`, NUNCA un archivo real.

## Mientras grabas, ¿está corriendo Streamlit?

Sí, ya lo arranqué. Verifica abriendo `http://localhost:8501` en el navegador.

Si no carga: doble clic en `lanzar_anonimizador.bat` y espera 10s.
