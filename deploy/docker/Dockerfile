FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/zertan/app/web_server \
    PORT=5050 \
    ZERTAN_DATA_DIR=/data \
    ZERTAN_DEBUG=0

WORKDIR /srv/zertan

COPY app/requirements.txt app/requirements.txt

RUN pip install --no-cache-dir -r app/requirements.txt \
    && adduser --disabled-password --gecos "" --home /home/zertan zertan \
    && mkdir -p /data \
    && chown -R zertan:zertan /srv/zertan /data

COPY app ./app
COPY README.md README.md

USER zertan

EXPOSE 5050

CMD ["sh", "-c", "gunicorn --chdir app/web_server --bind 0.0.0.0:${PORT:-5050} --workers ${GUNICORN_WORKERS:-2} --threads ${GUNICORN_THREADS:-4} --timeout ${GUNICORN_TIMEOUT:-120} wsgi:app"]
