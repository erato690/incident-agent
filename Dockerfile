FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1

COPY requirements.txt requirements-app.txt ./
RUN pip install --no-cache-dir -r requirements-app.txt

COPY agente/ agente/
COPY app/ app/
COPY dados/ dados/
COPY dados_dummy/ dados_dummy/
COPY scripts/ scripts/

EXPOSE 8501
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8501}
