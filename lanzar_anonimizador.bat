@echo off
REM Lanza la UI del Implica Anonimizador en el navegador por defecto.
REM Doble-clic para usar.

cd /d "%~dp0"

REM Comprueba que Python está instalado
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en PATH.
    echo Instala Python 3.11+ desde https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Comprueba que streamlit está instalado
python -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo [INFO] Instalando dependencias por primera vez...
    pip install -e . >nul 2>nul
    pip install streamlit pandas >nul 2>nul
    python -m spacy download es_core_news_md
)

echo.
echo ================================================
echo   Implica Anonimizador - Arrancando UI
echo ================================================
echo   Se abrira en el navegador en unos segundos.
echo   Para cerrar: cierra esta ventana negra.
echo ================================================
echo.

streamlit run streamlit_app.py --server.headless false --browser.gatherUsageStats false
