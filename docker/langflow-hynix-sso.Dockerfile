ARG LANGFLOW_HYNIX_BASE_IMAGE=dk02315/langflow-hynix:v1.10.0-hynix-sso-rc4
FROM ${LANGFLOW_HYNIX_BASE_IMAGE}

# The published Hynix SSO image currently misses this runtime dependency used by
# langflow.api.v1.login. Keep this as a thin compatibility wrapper so the base
# image can be swapped without vendoring Langflow source into this repository.
RUN /app/.venv/bin/pip install --no-cache-dir limits==5.6.0 slowapi==0.1.9
