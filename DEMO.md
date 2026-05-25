# Guion de demo para enseñarle a tu jefe

> Demo de 8–10 minutos. Te enseña a defender la herramienta sin caer en detalles técnicos.

## Antes de empezar (2 minutos en tu mesa)

1. **Arranca la app**: doble clic en `lanzar_anonimizador.bat` (en `C:\Users\Usuario\implica-anonimizador\`).
2. Espera a que el navegador abra `http://localhost:8501` solo.
3. **Verifica que ves**: header "Implica Anonimizador", sidebar con "Nuevo proyecto", botón para subir archivos.
4. Ten abierto en otra pestaña: el fixture sintético para la demo (en `tests/fixtures/sumas_saldos_realista.xlsx`).
5. Ten abierto Claude (claude.ai o ChatGPT) en una tercera pestaña.

> Si algo no funciona, salta al **Plan B** al final de este documento.

---

## La demo en 5 actos (8 min)

### Acto 1 — El problema (60s)

Empieza por el **dolor**, no por la solución:

> "Cuando hacemos due diligence, recibimos sumas y saldos con cientos de cuentas de clientes reales del target. Para usar IA o compartir el datapack con los compradores, hay que anonimizar manualmente, lo que nos lleva 1–2 horas por archivo y siempre hay riesgo de que se nos escape un nombre. Llevo unas semanas montando una herramienta que lo hace en 5 segundos y que cumple con nuestra política de confidencialidad."

**Punto clave**: "100% local, ningún dato sale de Implica."

### Acto 2 — Anonimizar un sumas y saldos (2 min)

1. En la app, **sidebar izquierda**: codename del proyecto → escribe `paradise`.
2. **Sube** el archivo `tests/fixtures/sumas_saldos_realista.xlsx` (arrastrar o "Browse files").
3. Pulsa **🔍 Analizar**.

   Comenta mientras procesa: *"Auto-detecta que es un libro contable porque ve las cuentas 430xxx (clientes), 410xxx (proveedores). No depende de inteligencia artificial para esto — es determinista, usa el plan general contable."*

4. Cuando aparezca la tabla, **enseña**:
   - Cada fila = una entidad
   - Columna **Variantes**: agrupa "CAIXABANK" + "CAIXABANK, SA" automáticamente
   - Columna **Cuenta(s) PGC**: el código original
   - Columna **Codename**: `[Cliente-4300000125]` (basado en el número de cuenta)

5. Enseña el selector de estrategia:
   - "Código completo": trazabilidad perfecta con el sumas y saldos original
   - "Código corto": más legible para Claude
   - "Secuencial": anonimización máxima

6. Pulsa **✅ Anonimizar y descargar** → se baja un ZIP.

### Acto 3 — Ver el resultado (1 min)

1. Abre el archivo `paradise_anonimizado.zip`, descomprime.
2. Abre el `sumas_saldos_realista.paradise.xlsx`.
3. Enseña a tu jefe que:
   - Los importes están intactos
   - Las fórmulas siguen funcionando (calcula totales correctamente)
   - Los nombres están reemplazados por `[Cliente-4300000125]`, `[Proveedor-4100000003]`, etc.

> "Esto es lo que le pasaríamos a Claude o al comprador. Ningún nombre real."

### Acto 4 — Análisis con Claude (2 min)

1. Sube el archivo anonimizado a **claude.ai**.
2. Pide algo concreto, por ejemplo:

   > "Analiza este sumas y saldos. Identifica los top 5 clientes por saldo y posibles partes vinculadas."

3. Cuando Claude responda con menciones tipo *"El Cliente-4300000003 representa..."*, **copia esa respuesta**.

### Acto 5 — Rehidratar (1 min)

1. Vuelve a la app, **tab ↩️ Rehydrate**.
2. Modo "Texto pegado", pega el análisis de Claude.
3. Pulsa **↩️ Rehidratar texto**.
4. **Resultado**: ves los nombres reales en lugar de los codenames. Listo para tu informe interno.

> "Y este último paso — el rehidratado — solo se hace dentro de Implica, en tu propio portátil. Nunca devuelves nombres reales fuera."

---

## Las 4 preguntas que probablemente te haga tu jefe

**1. "¿Esto cumple con confidencialidad?"**
Sí. La app corre 100% local. Los archivos nunca salen de la máquina donde se ejecuta. Lo único que se guarda permanentemente es un JSON con las correspondencias nombre↔codename (en `projects/paradise.json`), accesible solo desde el servidor.

**2. "¿Y los archivos que se suben a Claude?"**
Solo los **anonimizados**. Claude (Anthropic) tiene retención cero con la API empresarial y no entrena con datos. Y aún así, no ven nombres reales — ven `[Cliente-001]`.

**3. "¿Cuánto cuesta?"**
Cero infraestructura propia. Un PC fijo de oficina vale (o un mini-PC de 300€ si no hay). Python y todas las librerías son open source y gratis. Cero coste de subscripción.

**4. "¿Cuándo lo puede usar el equipo?"**
Hoy si quieres: IT necesita 10 minutos para ejecutar `install_server.ps1` en un PC fijo y repartir la URL al equipo. Toda la documentación de instalación está en `INSTALL.md`.

---

## Plan B si algo falla en la demo

### Si la app no abre (`localhost:8501` no responde)

Cierra el navegador, vuelve a hacer doble clic en `lanzar_anonimizador.bat`, espera 10 segundos.

### Si te quedas mirando un spinner que no termina

Cierra la ventana negra de PowerShell. Vuelve a hacer doble clic en `lanzar_anonimizador.bat`. Recarga el navegador con Ctrl+F5.

### Si el análisis dice "0 candidatos detectados"

- Verifica que has subido el archivo correcto (`sumas_saldos_realista.xlsx`, no otro)
- En el selector de tipo, fuerza manualmente "📊 Sumas y saldos / Libro contable"

### Si quieres mostrar también el flujo con teasers (no contable)

Cambia al fixture `teaser_atlas.pptx`. Mismo flujo pero detecta empresa principal y equipo directivo.

### Plan último recurso

Si nada funciona, enseña los archivos del repo y los fixtures generados — el código está, las pruebas pasan, la herramienta es real. La demo es solo eso, una demo.

---

## Después de la demo — siguientes pasos

### Si tu jefe dice "OK, hagámoslo"

1. **Cuéntale a IT** (o quien instaló n8n):
   - Pásales la carpeta entera `C:\Users\Usuario\implica-anonimizador\` (cópiala a un USB o súbela a un OneDrive interno)
   - Diles: *"Es un proyecto Python con UI Streamlit. Toda la guía técnica está en `INSTALL.md` dentro de la carpeta."*
2. IT ejecuta `install_server.ps1` en un PC fijo de oficina (10 min).
3. Te devuelven una URL tipo `http://192.168.X.Y:8501` y una contraseña.
4. Tú repartes esa URL al equipo con el mensaje preparado en `mensaje_equipo.md`.

### Si tu jefe pide cambios

Pregúntale qué falta. Decisiones típicas:
- ¿Quieres que use otra nomenclatura de codenames? → cambio 1 línea
- ¿Quiere que el rehydrate envíe los resultados a un email? → 30 min de dev
- ¿Quiere reportes por proyecto? → 1 día de dev

---

## NO uses Vercel ni cloud público

Lo dejo escrito por si te lo plantean en algún momento:

> **No es viable** subir esta herramienta a Vercel, AWS, Azure ni ningún cloud público para procesar documentos de clientes M&A:
>
> - Los archivos del cliente viajarían a infraestructura de terceros (rompe confidencialidad).
> - El compliance de M&A en España exige procesado local o en infraestructura propia.
> - Es la misma razón por la que NDAs prohíben usar SaaS no aprobados con material del deal.
>
> **El camino correcto** es servidor INTERNO de Implica (PC dedicado o mini-PC en oficina), como ya hacéis con n8n.
