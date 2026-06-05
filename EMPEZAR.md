# 🚀 Empezar (para gente que no es programadora)

> Si nunca has tocado código, esta guía es para ti. **30 minutos** y tendrás todo funcionando. Sigue los pasos en orden, no te saltes ninguno.

---

## ¿Qué es esto y qué voy a hacer?

Vas a instalar una **herramienta** llamada **Claude Code** en tu portátil. Es como un programador que vive dentro de tu Terminal y al que le das órdenes en español:

> "Descarga el proyecto del anonimizador y déjamelo listo para usar"

Y él lo hace solo: descarga, instala, configura. Tú solo le hablas.

Para que Claude Code funcione, primero necesitas instalar 3 cosas básicas (Python, Node, Git). Son **3 instaladores normales**, como cuando instalas Chrome. Le das siguiente, siguiente, siguiente.

**Tiempo total:** ~30 minutos. La mayor parte es esperar a que se instale solo.

---

## Paso 1 — Instalar Python (5 minutos)

Python es el "lenguaje" en el que está escrita la herramienta.

1. Ve a 👉 **https://www.python.org/downloads/**
2. Verás un botón amarillo grande que dice **"Download Python 3.x.x"** (la versión que sea, pero asegúrate que sea **3.11 o superior**).
3. Click → se descarga un `.exe`
4. Ábrelo (doble clic)
5. **⚠️ IMPORTANTE — antes de pulsar "Install Now"**: abajo del todo hay una casilla `☐ Add python.exe to PATH`. **Márcala**. Si no la marcas, no va a funcionar.
6. Pulsa "Install Now"
7. Espera. Cuando termine, cierra la ventana.

### ¿Cómo sé si Python está bien instalado?

1. Pulsa la tecla **Windows** del teclado
2. Escribe `cmd` y dale Enter (te abre una ventana negra llamada "Símbolo del sistema")
3. Escribe:
   ```
   python --version
   ```
4. Pulsa Enter. Debe decir algo como `Python 3.11.7` o `Python 3.12.x`.

Si dice eso → ✅ vas bien. Cierra la ventana negra.

Si dice `'python' no se reconoce...` → no marcaste la casilla del Path. Desinstala Python y vuelve al paso 5 con la casilla marcada.

---

## Paso 2 — Instalar Node.js (3 minutos)

Node.js es necesario para instalar Claude Code.

1. Ve a 👉 **https://nodejs.org/**
2. Verás dos botones grandes. Pulsa el de la **izquierda** (el que dice **"LTS"** — son las siglas de "estable").
3. Se descarga un `.msi` → ábrelo
4. Siguiente, siguiente, siguiente. Acepta todo lo que te pida.
5. Cuando termine, **cierra todas las ventanas del símbolo del sistema** que tengas abiertas.

### ¿Cómo sé si está bien?

1. Abre una NUEVA ventana negra (Windows → cmd → Enter)
2. Escribe:
   ```
   node --version
   ```
3. Debe decir algo como `v20.10.0` (o más alto).

Si dice eso → ✅ vas bien.

---

## Paso 3 — Instalar Git (3 minutos)

Git es la herramienta que descarga proyectos desde GitHub.

1. Ve a 👉 **https://git-scm.com/download/win**
2. Se descarga solo. Cuando termine, ábrelo.
3. **Acepta TODO lo que te pida sin cambiar nada**. Solo pulsa "Next" hasta el final, y luego "Install".
4. Cuando termine, cierra la ventana.

### ¿Cómo sé si está bien?

1. Abre una NUEVA ventana negra (Windows → cmd → Enter)
2. Escribe:
   ```
   git --version
   ```
3. Debe decir algo como `git version 2.43.0`.

Si dice eso → ✅ ya tienes la base lista.

---

## Paso 4 — Instalar Claude Code (2 minutos)

1. Abre el símbolo del sistema (Windows → cmd → Enter)
2. Copia y pega esta línea (clic derecho en la ventana negra para pegar):
   ```
   npm install -g @anthropic-ai/claude-code
   ```
3. Pulsa Enter. Verás texto pasando durante 30-60 segundos. **NO cierres la ventana**.
4. Cuando se quede quieto y veas el cursor parpadear listo, está instalado.

### ¿Cómo sé si está bien?

En la misma ventana negra escribe:
```
claude --version
```

Debe decir algo como `claude 0.x.x`. Si dice eso → ✅ Claude Code está instalado.

---

## Paso 5 — Cuenta para Claude (5 minutos)

> ⚠️ **OJO — Anthropic tiene DOS productos distintos con cuentas separadas. NO los confundas.**

| Producto | URL | Tipo de pago | Para qué |
|---|---|---|---|
| **Claude.ai** | https://claude.ai | Suscripción mensual fija ($20-200/mes) | Lo que usamos aquí. **ESTA es la que necesitas.** |
| Console (API) | https://console.anthropic.com | Créditos prepago (pay-as-you-go) | API directa para desarrolladores. **NO la necesitas para Claude Code.** |

### Lo que tienes que hacer

1. Ve a 👉 **https://claude.ai** (la web normal de Claude)
2. **Sign up** si no tienes cuenta, o **Log in** si ya la tienes
3. Si vas a usar Claude Code de verdad para este proyecto, suscríbete a **Claude Pro ($20/mes)** desde https://claude.ai/upgrade
   - Es la opción más simple y predecible para uso normal
   - Para este proyecto Pro te llega de sobra
4. Anota tu email y contraseña — los vas a necesitar en el paso siguiente

> 💰 **Antes de pagar**: pregunta a Ricardo o IT si Implica tiene una cuenta corporativa que puedas usar.
>
> **¿Y la "consola de Anthropic" (console.anthropic.com)?** Es otro producto distinto, con créditos prepago. Si entras ahí, te va a pedir cargar dinero — **ciérrala**. Para Claude Code lo que necesitas es Claude.ai (paso de arriba), no la consola.

---

## Paso 6 — Arrancar Claude Code por primera vez (2 minutos)

1. Abre una NUEVA ventana negra (Windows → cmd → Enter)
2. Cambia a tu carpeta de usuario:
   ```
   cd C:\Users\%USERNAME%
   ```
3. Crea una carpeta donde vivirán tus proyectos:
   ```
   mkdir proyectos
   cd proyectos
   ```
4. Arranca Claude Code:
   ```
   claude
   ```
5. La PRIMERA vez te pedirá login. Te dará varias opciones — **MUY IMPORTANTE elegir bien**:

   | Opción que ves | Qué elegir |
   |---|---|
   | ✅ **"Sign in with Claude"** o **"Use Claude subscription"** | ELIGE ESTA |
   | ❌ "Use API key" | NO uses esta — te llevará a comprar créditos en consola |
   | ❌ "Use Anthropic Console" | NO uses esta — mismo problema |

6. Se abrirá el navegador automáticamente. Loguéate con la cuenta de **Claude.ai** del paso 5 (la que tiene Pro si lo activaste).
7. Vuelves a la ventana negra. Ya estás dentro de Claude Code. Verás un cursor parpadeando esperando que escribas algo.

### ⚠️ Si te aparece una pantalla de "Compra créditos de uso"

Significa que has caído en la **Console** (API) en vez de Claude.ai. Esto es lo que tienes que hacer:

1. Cierra esa pantalla de pago.
2. En la ventana negra de Claude Code, pulsa **Ctrl+C** para salir.
3. Vuelve a escribir `claude` y dale Enter.
4. Esta vez, cuando te pregunte cómo autenticarte, elige **"Sign in with Claude"** (NO "API key" ni "Console").
5. Te llevará a la web normal de claude.ai, no a la consola.
6. Si después de esto sigue pidiéndote créditos, es porque no tienes suscripción Pro/Max. Suscríbete en https://claude.ai/upgrade ($20/mes) y vuelve a este paso.

### ⚠️ Si al ejecutar `claude` ya entras directamente sin que te pregunte login

Quiere decir que **ya estás logueado con la cuenta equivocada** (la API/Console de antes). Para cambiar de cuenta:

**Opción 1 (más fácil):** Dentro de Claude Code escribe:
```
/logout
```
Pulsa Enter. Te confirma que has salido y se cierra. Vuelve a escribir `claude` y esta vez te pregunta cómo autenticarte de nuevo.

**Opción 2 (si /logout no funciona):** Cierra Claude Code (Ctrl+C dos veces) y borra la cache:
```
rmdir /s /q "%USERPROFILE%\.claude"
```
Confirma con `y` + Enter. Luego ejecuta `claude` otra vez. Empieza de cero.

> Esto solo borra el login local de Claude Code, NO borra nada de tu PC ni de tus proyectos.

---

## Paso 7 — El prompt mágico (10-15 minutos, casi todo es esperar)

Aquí es donde Claude Code hace TODO el trabajo por ti. Vas a pegarle un mensaje largo y él va a:

1. Descargar el proyecto del anonimizador
2. Instalar todas las dependencias
3. Descargar el modelo de inteligencia artificial en español
4. Arrancar la aplicación
5. Decirte que está lista

### Copia este prompt entero y pégalo en Claude Code:

```
Necesito que prepares el proyecto "Implica Anonimizador" en este equipo. Sigue
estos pasos en orden y avísame si algo falla:

1. Clona el repositorio https://github.com/reck05/implica-anonimizador.git
   en la carpeta actual.

2. Entra a la carpeta implica-anonimizador.

3. Lee el archivo CLAUDE.md para entender el contexto del proyecto y el archivo
   ONBOARDING.md para los pasos de setup.

4. Crea un entorno virtual de Python (.venv) y actívalo.

5. Instala el paquete en modo editable con pip install -e .

6. Descarga el modelo de spaCy en español con python -m spacy download
   es_core_news_md (tarda 1-2 minutos, son ~40MB).

7. Corre el test python tests/test_round_trip.py para verificar que todo
   funciona. Debe terminar con "✓✓✓ Round-trip test PASS". Si falla, diagnostícalo.

8. Cuando termines, no arranques Streamlit todavía — solo dime que está todo
   listo y dame el comando exacto para arrancarlo cuando yo quiera.

REGLAS IMPORTANTES de este proyecto (están en CLAUDE.md):
- Nunca commitees datos reales de clientes
- Los archivos del cliente nunca deben acabar dentro de la carpeta del proyecto
- Si yo te paso un archivo de cliente para procesar, recuérdamelo antes de
  hacer nada raro con él

Cuando termines todo, dime "Setup completado" y un resumen de qué hiciste.
```

### Mientras espera

Claude Code te irá enseñando lo que hace. Algunas veces te preguntará:

- *"¿Puedo ejecutar este comando?"* → di **"sí"**
- *"¿Puedo escribir este archivo?"* → di **"sí"**

Si te dice "Setup completado" → ✅ todo listo, ve al paso 8.

Si algo falla, **copia el error y pégaselo a Claude Code** diciendo "esto ha fallado, arréglalo". Él se encarga.

---

## Paso 8 — Arrancar la aplicación

Cuando Claude Code te diga que está todo listo:

1. En la misma ventana de Claude Code, escribe:
   ```
   Arranca Streamlit con: streamlit run streamlit_app.py
   ```
2. Pulsa Enter. Verás texto pasando y luego dirá algo como:
   ```
   You can now view your Streamlit app in your browser.
   Local URL: http://localhost:8501
   ```
3. Se abrirá tu navegador automáticamente con la aplicación.
4. Si no se abre, abre tu navegador (Chrome / Edge) y ve a:
   ```
   http://localhost:8501
   ```

### Cómo probar que funciona

1. En la barra lateral izquierda escribe un codename, por ejemplo: `prueba`
2. En el centro, arrastra el archivo:
   ```
   C:\Users\%USERNAME%\proyectos\implica-anonimizador\tests\fixtures\sumas_saldos_realista.xlsx
   ```
3. Pulsa "🔍 Analizar"
4. Espera 30 segundos
5. Verás una tabla con todos los clientes/proveedores detectados
6. Pulsa "✅ Anonimizar y descargar"
7. Se baja un ZIP con el archivo anonimizado

Si llegas hasta aquí → ✅ **TIENES EL PROYECTO FUNCIONANDO**. Felicidades.

---

## Paso 9 — Mañana (cómo lo abro otra vez)

Cuando vuelvas mañana y quieras seguir trabajando:

### Para usar la app

1. Abre el explorador de archivos en:
   ```
   C:\Users\%USERNAME%\proyectos\implica-anonimizador\
   ```
2. Doble clic en `lanzar_anonimizador.bat`
3. Se abre el navegador con la app

### Para trabajar con Claude Code (modificar el código)

1. Abre cmd (Windows → cmd → Enter)
2. Escribe:
   ```
   cd C:\Users\%USERNAME%\proyectos\implica-anonimizador
   claude
   ```
3. Estás dentro. Pídele lo que quieras hacer.

---

## Cosas importantes que tienes que saber

### 🛡️ Confidencialidad — léelo de verdad

Este proyecto procesa documentos de clientes de Implica. Hay **una regla sagrada**:

> **NUNCA** copies archivos del cliente (xlsx, pdf, docx) DENTRO de la carpeta del proyecto.

Si quieres procesar un archivo real de un cliente:
1. Déjalo donde está (probablemente en tu OneDrive de Implica)
2. Súbelo a la app desde el navegador (botón "Browse files")
3. La app lo procesa en memoria y te devuelve el resultado
4. **NO arrastres archivos del cliente dentro de la carpeta `implica-anonimizador/`**

¿Por qué? Porque si por error ejecutas `git push`, ese archivo podría acabar en GitHub público.

### 🤖 Cómo le hablo a Claude Code

Imagina que estás escribiendo a un compañero programador por chat. Sé claro y específico:

| ❌ Mal | ✅ Bien |
|---|---|
| "haz que funcione mejor" | "El test test_pgc.py tarda 10 segundos. ¿Puedes optimizar la función _find_header_row para que tarde menos de 2 segundos?" |
| "añade colores" | "En la UI de Streamlit (streamlit_app.py), cambia el color del botón 'Anonimizar' de azul a verde Implica (#0066CC)" |
| "arregla esto" + screenshot | "Cuando subo un PDF de 100 páginas, la app se queda en 'Analizando...' más de 5 minutos. Diagnostica por qué y arréglalo" |

### 📦 Cómo subir tus cambios al repo de GitHub

Si haces cambios al código y quieres compartirlos:

1. En Claude Code escribe:
   ```
   Quiero subir mis cambios al repo. Hazlo con un commit descriptivo y push.
   Pero primero verifica que no haya archivos confidenciales en lo que vas a commitear.
   ```
2. Claude Code te enseñará qué va a subir y te pedirá confirmación. Lee bien y di "sí" solo si todo es código (no archivos de cliente).

### 🆘 Si algo se rompe

Lo bueno de Claude Code: si rompes algo, le dices "deshaz mis últimos cambios" y lo hace.

Lo bueno de Git: cada cambio queda registrado. Puedes volver a cualquier versión anterior.

**No tengas miedo de probar cosas.** En el peor caso, borras la carpeta entera, vuelves al paso 6 y empiezas otra vez (10 min).

---

## Resumen visual

```
┌──────────────────────────────────────────┐
│ Paso 1: Python (5 min) ✅                │
│ Paso 2: Node.js (3 min) ✅               │
│ Paso 3: Git (3 min) ✅                   │
│ Paso 4: Claude Code (2 min) ✅           │
│ Paso 5: Cuenta Anthropic (5 min) ✅      │
│ Paso 6: Arrancar Claude Code (1 min) ✅  │
│ Paso 7: Pegar el prompt mágico (15 min) ✅│
│ Paso 8: Probar la app (5 min) ✅         │
│ ─────────────────────────────────────── │
│ TOTAL: ~30 minutos                       │
└──────────────────────────────────────────┘
```

---

## A quién pregunto si algo no funciona

1. **Primero**: pídele ayuda a Claude Code. En serio. Es para lo que está.
2. **Si Claude Code no sabe**: pregúntale a Ricardo
3. **Si es problema de Windows / red de oficina**: IT

---

¡Bienvenido al proyecto! Cuando termines el paso 8 con éxito, mándale un mensaje a Ricardo diciendo "ya está funcionando" para que sepa que está todo OK.
