# Imagen para desplegar el Implica Anonimizador en Azure App Service (Linux, contenedores)
# o Azure Container Apps. Streamlit + spaCy es_core_news_md preinstalado.
FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema (PyMuPDF trae wheels, pero dejamos lo mínimo por robustez)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python primero (capa cacheable)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download es_core_news_md

# Copiar el resto del proyecto e instalar el paquete
COPY . .
RUN pip install --no-cache-dir -e .

# Streamlit detrás del proxy de Azure: headless, sin CORS/XSRF (los maneja el proxy)
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

EXPOSE 8501

# Azure App Service espera que la app escuche en el puerto de WEBSITES_PORT (8501 abajo).
CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=false"]
