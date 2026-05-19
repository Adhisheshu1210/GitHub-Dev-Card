FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy the backend requirements first for better caching
COPY backend/requirements.txt ./backend/
RUN uv pip install --system -r backend/requirements.txt

# Copy the entire project so backend and frontend exist
COPY . .

# Set working directory to backend where main.py lives
WORKDIR /app/backend

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
