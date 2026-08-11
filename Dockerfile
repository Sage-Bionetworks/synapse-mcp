FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for cryptographic libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create an unprivileged user to run the application
RUN groupadd --system synapse && useradd --system --gid synapse --home /app synapse \
    && chown synapse:synapse /app

# uv installs the exact versions recorded in uv.lock
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv

# Copy the project files, owned by the runtime user
COPY --chown=synapse:synapse . .

# Drop root before installing so the virtualenv belongs to the runtime user
USER synapse

RUN uv sync --frozen --no-dev --no-editable --no-cache --python-preference only-system

ENV PATH="/app/.venv/bin:$PATH"

# Expose the port
EXPOSE 9000

# Set environment variables
ENV HOST="0.0.0.0"
ENV PORT="9000"

# Command to run the server
CMD ["python", "-m", "synapse_mcp"]
