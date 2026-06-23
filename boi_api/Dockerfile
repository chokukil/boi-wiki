FROM python:3.11-slim

ARG BOI_BUILD_REVISION=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOI_BUILD_REVISION=${BOI_BUILD_REVISION}

LABEL org.opencontainers.image.revision="${BOI_BUILD_REVISION}"

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY app /app/app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
