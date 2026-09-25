FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY boi_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
ARG BOI_BUILD_REVISION=dev-local
ENV BOI_BUILD_REVISION=${BOI_BUILD_REVISION}
LABEL org.opencontainers.image.revision="${BOI_BUILD_REVISION}"
COPY boi_api/app /app/boi_api/app
COPY agent_kit /app/agent_kit
COPY data/agent_catalog /app/data/agent_catalog
COPY data/ontology /app/data/ontology
COPY data/boi/public/harness /app/data/boi/public/harness
COPY scripts/initialize_mcp_state.py /app/scripts/initialize_mcp_state.py
EXPOSE 8000
CMD ["uvicorn", "boi_api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
