FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY migrations ./migrations
COPY assets ./assets
RUN uv sync --locked --no-dev && useradd --uid 10001 --create-home bot && mkdir -p /app/data/audio /app/data/catalogue && chown -R bot:bot /app/data
USER bot
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1
ENTRYPOINT ["python","-m","elevenbot"]
CMD ["worker"]
