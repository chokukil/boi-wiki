FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY boi_wiki_mcp/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY boi_wiki_mcp/app /app/boi_wiki_mcp/app
COPY agent_kit /app/agent_kit
EXPOSE 8200
CMD ["uvicorn", "boi_wiki_mcp.app.main:app", "--host", "0.0.0.0", "--port", "8200"]
