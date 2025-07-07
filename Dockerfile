FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Run Streamlit on port 8000 (public) and FastAPI internally on 8501
CMD ["bash", "-c", "uvicorn app:app --host 0.0.0.0 --port=8501 & streamlit run streamlit.py --server.port=8000 --server.enableCORS=false --server.enableXsrfProtection=false"]
