FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
COPY src/ /app/src/
RUN python -m lumentrail init && \
    chown -R 65532:65532 /app/data && \
    chmod 600 /app/data/lumentrail.db
USER 65532:65532
EXPOSE 8080
CMD ["python", "-m", "lumentrail", "--database", "/app/data/lumentrail.db", "serve", "--host", "0.0.0.0"]

