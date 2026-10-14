FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && groupadd --gid 10001 logistics && useradd --uid 10001 --gid logistics --no-create-home logistics
COPY --chown=logistics:logistics . .
RUN mkdir -p /app/.telegram_session /app/staticfiles && chown -R logistics:logistics /app/.telegram_session /app/staticfiles
USER logistics
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
