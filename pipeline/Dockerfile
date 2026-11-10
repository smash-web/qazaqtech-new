FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY qtnews ./qtnews
RUN useradd -r -u 10001 bot && chown -R bot /app
USER bot
CMD ["python", "-m", "qtnews.main", "run"]
