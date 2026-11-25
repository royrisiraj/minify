FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    && useradd --create-home --uid 10001 minify
COPY --chown=minify:minify app ./app
COPY --chown=minify:minify migrations ./migrations
COPY --chown=minify:minify alembic.ini ./
USER minify
EXPOSE 8000
CMD ["python", "-m", "app"]
