FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

CMD ["bash", "-c", "uvicorn app:app --host 0.0.0.0 --port=8000 & streamlit run streamlit.py --server.port=8501 --server.enableCORS=false"]
