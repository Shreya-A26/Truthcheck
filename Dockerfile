# TruthLens Production Dockerfile for Render Deployment
# Multi-runtime container supporting Python 3.11 (Flask ML backend) and Node.js 20 LTS (Tesseract OCR runner)

FROM python:3.11-slim

# Prevent interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NODE_ENV=production \
    PORT=10000

WORKDIR /app

# 1. Install base system dependencies, Node.js 20 LTS, and shared libraries required by OpenCV/ONNX
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    tesseract-ocr \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Node.js dependencies for local offline OCR (tesseract.js)
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# 3. Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy application source, models, services, reports, static, and templates
COPY app.py config.py ./
COPY models/ ./models/
COPY services/ ./services/
COPY reports/ ./reports/
COPY static/ ./static/
COPY templates/ ./templates/

# 5. Create instance directories for SQLite database and ephemeral uploads
RUN mkdir -p /app/instance/uploads && chmod -R 777 /app/instance

# Expose the application port
EXPOSE $PORT

# 6. Launch with Gunicorn (1 worker with 4 threads for memory safety within 512 MB RAM limits)
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile - app:app"]
