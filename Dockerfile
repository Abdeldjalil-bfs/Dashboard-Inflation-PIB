FROM python:3.11-slim

WORKDIR /app

# Le fichier requirements installe aussi le projet (« -e . ») : le code doit
# être copié avant l'installation.
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8501
CMD ["streamlit", "run", "app/Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
