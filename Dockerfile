# Pick a base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv as per official docs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy uv project configuration
COPY pyproject.toml .
COPY uv.lock .
COPY .python-version .

# Copy project files
COPY notebooks/* notebooks/
COPY src/* src/

# Install dependencies with uv
RUN uv sync

# run main.py inside the notebooks folder
CMD ["uv", "run", "python", "src/main.py"]