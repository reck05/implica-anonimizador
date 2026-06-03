# Onboarding — para el compañero que se hereda este proyecto

> Esta guía te lleva de cero a tener el proyecto corriendo en tu portátil + Claude Code listo para que trabajes con él como hizo Ricardo. **~30-45 minutos** en total.

## TL;DR

1. Instalas Python 3.11, Git, Node.js (10 min)
2. Instalas Claude Code (5 min)
3. Clonas el repo y arrancas la app (5 min)
4. Abres Claude Code en la carpeta y empiezas (instantáneo — el archivo `CLAUDE.md` ya tiene todo el contexto)

---

## 1. Software base (10 min)

Descarga e instala en orden:

### 1.1 Python 3.11

- Ve a https://www.python.org/downloads/
- **IMPORTANTE**: marca "Add Python to PATH" durante la instalación
- Versión exacta recomendada: **3.11.x** (el proyecto está fijado a 3.11 en `runtime.txt`)
- Verifica:
  ```powershell
  python --version
  # Debe decir: Python 3.11.x
  ```

### 1.2 Git

- Descarga: https://git-scm.com/download/win
- Acepta los defaults durante la instalación
- Verifica:
  ```powershell
  git --version
  ```

### 1.3 Node.js (para Claude Code)

- Descarga LTS: https://nodejs.org/
- Verifica:
  ```powershell
  node --version
  npm --version
  ```

### 1.4 VS Code (opcional pero recomendado)

- https://code.visualstudio.com/
- Para editar el código manualmente cuando no uses Claude Code.

---

## 2. Instalar Claude Code (5 min)

Claude Code es la CLI con la que se desarrolló este proyecto. Hace de "pair programmer" usando Claude.

### 2.1 Instalar

```powershell
npm install -g @anthropic-ai/claude-code
```

### 2.2 Verificar

```powershell
claude --version
```

### 2.3 Autenticarte

```powershell
claude
```

La primera vez te abre el navegador para que inicies sesión con tu cuenta de Anthropic. Si no tienes, créatela en https://console.anthropic.com/.

> **Coste**: Claude Code tiene plan gratuito limitado, y plan Pro ($20/mes) o Max ($100-200/mes) según uso. Ricardo te puede decir qué plan está usando Implica.

---

## 3. Clonar el proyecto (5 min)

### 3.1 Elige una carpeta donde vivirá el proyecto

```powershell
cd C:\Users\<tu-usuario>\
mkdir proyectos
cd proyectos
```

### 3.2 Clona el repo

```powershell
git clone https://github.com/reck05/implica-anonimizador.git
cd implica-anonimizador
```

### 3.3 Configura tu identidad en git

```powershell
git config user.name "Tu Nombre"
git config user.email "tu.email@implicacf.com"
```

---

## 4. Setup del proyecto (10 min)

### 4.1 Crear entorno virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> Si te da error de "execution policy", ejecuta una vez:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

Verás `(.venv)` al principio del prompt cuando esté activado.

### 4.2 Instalar dependencias

```powershell
pip install --upgrade pip
pip install -e .
python -m spacy download es_core_news_md
```

> La descarga del modelo spaCy son ~40 MB. La primera vez tarda un minuto.

### 4.3 Arrancar la app por primera vez

```powershell
streamlit run streamlit_app.py
```

Te abre el navegador en `http://localhost:8501`. **Pruébalo subiendo el fixture sintético**:
- `tests/fixtures/sumas_saldos_realista.xlsx`

Si ves la tabla de candidatos y todo va bien, la app está funcional en tu portátil. Cierra el navegador y para Streamlit con `Ctrl+C`.

### 4.4 Verificar con los tests

```powershell
python tests/test_round_trip.py
python tests/test_pgc.py
```

Ambos deben terminar con `✓✓✓ ... PASS`.

---

## 5. Primera sesión con Claude Code (5 min)

### 5.1 Abre el proyecto en Claude Code

Desde PowerShell, en la carpeta del proyecto:

```powershell
cd C:\Users\<tu-usuario>\proyectos\implica-anonimizador
claude
```

Claude Code arranca y **lee automáticamente** `CLAUDE.md`, que contiene:
- Arquitectura del proyecto
- Reglas de confidencialidad
- Comandos típicos
- Convenciones

No tienes que explicarle nada a Claude. Solo dile lo que quieres hacer.

### 5.2 Prueba un comando inicial

Pídele algo simple para verificar:

```
Lista los archivos principales del proyecto y resume qué hace cada uno.
```

Claude te responderá con el contexto del CLAUDE.md. Si funciona, listo.

### 5.3 Estilo de prompts efectivos

Claude Code funciona mejor cuando le das contexto + tarea concreta:

| ❌ Vago | ✅ Específico |
|---|---|
| "arregla esto" | "El test `test_pgc.py` falla en la línea 87. El error dice que `account_codes` está vacío. Diagnóstica y arregla." |
| "haz que vaya más rápido" | "El procesado de un Excel de 100k filas tarda 2 minutos. Profílalo y propón optimizaciones." |
| "añade login" | "Necesito un login con usuario+contraseña por usuario (multi-usuario). Hoy es solo una contraseña global. Diséñalo, dame el plan en plan mode antes de implementar." |

### 5.4 Comandos útiles dentro de Claude Code

- `/help` — ayuda general
- `/clear` — limpia el contexto de la conversación actual
- `/cost` — ver cuánto llevas gastado en la sesión
- `/permissions` — gestionar qué puede hacer (ejecutar bash, escribir archivos, etc.)
- `Ctrl+C` o escribe `exit` — salir

---

## 6. Cosas importantes que tienes que saber

### 6.1 Confidencialidad — la regla de oro

El archivo `CLAUDE.md` lo deja claro pero te lo repito:

**JAMÁS** commitear:
- `projects/*.json` (contienen nombres reales de clientes)
- Archivos `.xlsx/.docx/.pptx/.pdf` excepto los de `tests/fixtures/`

Si necesitas probar con un archivo real:
- Copia el archivo a una carpeta **FUERA** del repo (ej. `C:\temp\`)
- Procesa
- Borra al terminar
- **NUNCA** lo metas dentro de la carpeta `implica-anonimizador/`

### 6.2 Cómo arrancar la app día a día

Opción A — doble clic:
```
C:\Users\<tu-usuario>\proyectos\implica-anonimizador\lanzar_anonimizador.bat
```

Opción B — PowerShell:
```powershell
cd C:\Users\<tu-usuario>\proyectos\implica-anonimizador
.\.venv\Scripts\Activate.ps1
streamlit run streamlit_app.py
```

### 6.3 Cómo subir cambios al repo

```powershell
git add .
git commit -m "Descripción corta de qué cambiaste"
git push
```

> Si modificas algo crítico (detectores, accounting, mapping), corre primero los tests:
> ```powershell
> python tests/test_round_trip.py
> python tests/test_pgc.py
> ```

### 6.4 Cómo actualizar tu copia con cambios de otros

```powershell
git pull
pip install -e .  # por si añadieron dependencias
```

### 6.5 Versiones desplegadas

| Versión | URL | Para qué |
|---|---|---|
| Tu portátil | `http://localhost:8501` | Trabajo diario con datos reales |
| Servidor interno Implica | (URL la tiene IT) | Equipo entero |
| Streamlit Cloud (demo) | `https://implica-anonimizador.streamlit.app` (ejemplo) | Solo demos, no datos reales |

---

## 7. Documentación adicional

| Archivo | Para qué |
|---|---|
| [`README.md`](README.md) | Visión general del proyecto |
| [`CLAUDE.md`](CLAUDE.md) | Contexto que Claude Code lee solo |
| [`USER_GUIDE.md`](USER_GUIDE.md) | Cómo usar la UI (para usuarios finales) |
| [`INSTALL.md`](INSTALL.md) | Instalación en servidor (para IT) |
| [`DEMO.md`](DEMO.md) | Guion de demo en vivo |
| [`DEMO_VIDEO.md`](DEMO_VIDEO.md) | Guion de demo grabada (Loom) |
| [`mensaje_equipo.md`](mensaje_equipo.md) | Plantillas de comunicación |

---

## 8. Preguntas que probablemente tengas

**¿Por qué Streamlit y no Next.js / FastAPI?**
Porque la UX de "subir archivos → procesar → descargar" se hace en 200 líneas con Streamlit. Para datos confidenciales que no salen del servidor, Streamlit es la opción óptima.

**¿Por qué Python 3.11 y no 3.13?**
spaCy 3.7 (que estamos usando) no tiene wheels para 3.13. Cuando spaCy 3.8+ esté estable y testeado, podemos subir.

**¿Por qué no Vercel / AWS / cloud?**
Confidencialidad M&A. Los datos no pueden salir de la infraestructura interna de Implica. Solo Streamlit Cloud para demos con fixtures sintéticos.

**¿Puedo añadir tests con pytest formal?**
Sí. Los actuales son scripts directos porque era más rápido de iterar. Si los conviertes a pytest, mantén los nombres `test_*.py`.

**¿Qué pasa si Claude Code se equivoca y rompe algo?**
`git status` para ver qué cambió. `git checkout -- archivo.py` para deshacer cambios en un archivo. `git stash` para guardar y revisar después.

---

## 9. A quién preguntar

- **Ricardo (autor)**: dudas funcionales del producto, decisiones de diseño
- **IT de Implica**: despliegue en servidor, problemas de instalación corporativa
- **Claude Code (en la CLI)**: dudas técnicas del código — describe el problema y te ayuda

---

¡Bienvenido al proyecto!
