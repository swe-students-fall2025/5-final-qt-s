FROM python:3.11-slim

WORKDIR /app

COPY service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY service/ service/

CMD ["python", "-m", "service.app"]
