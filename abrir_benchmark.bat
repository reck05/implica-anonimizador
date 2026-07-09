@echo off
REM Abre el informe del benchmark en el navegador. Si no existe, lo genera primero.
cd /d "%~dp0"

if not exist "benchmark_outputs\benchmark_resultado.html" (
    echo Generando el benchmark por primera vez...
    python tests\benchmark_gliner.py
)

if exist "benchmark_outputs\benchmark_resultado.html" (
    echo Abriendo informe en el navegador...
    start "" "benchmark_outputs\benchmark_resultado.html"
) else (
    echo No se pudo generar el informe. Revisa que Python este instalado.
    pause
)
