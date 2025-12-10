FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY service/ service/
COPY templates/ templates/
COPY static/ static/
COPY mongo/ mongo/

CMD ["python", "-m", "api.app"]
