FROM python:3.11-slim

WORKDIR /app

# install deps
COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY service/ service/

COPY mongo/seed.py mongo/seed.py
COPY mongo/seed_data.json mongo/seed_data.json

CMD ["python", "-m", "api.app"]
