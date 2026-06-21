FROM python:3.11-slim

# Install system dependencies: FFmpeg, WeasyPrint (Pango, Cairo, GDK-Pixbuf), yt-dlp
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libcairo2 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create temp directory for job processing
RUN mkdir -p /tmp/mediawatch-jobs

CMD ["python", "-m", "src.main"]
