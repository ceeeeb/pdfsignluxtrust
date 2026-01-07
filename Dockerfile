FROM python:3.11-slim-bookworm

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for Qt, PDF rendering, smart card and Java
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Qt/PySide6 dependencies
    libgl1-mesa-glx \
    libegl1-mesa \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb1 \
    libx11-xcb1 \
    libxcb-util1 \
    libdbus-1-3 \
    libfontconfig1 \
    libfreetype6 \
    libglib2.0-0 \
    # Smart card / PKCS#11 support
    pcscd \
    libpcsclite1 \
    libpcsclite-dev \
    pcsc-tools \
    opensc \
    # Java Runtime for signing
    default-jre-headless \
    # Useful utilities
    usbutils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -s /bin/bash pdfsigner && \
    mkdir -p /app /home/pdfsigner/Documents /app/java-signer && \
    chown -R pdfsigner:pdfsigner /app /home/pdfsigner

WORKDIR /app

# Copy requirements first for better caching
COPY --chown=pdfsigner:pdfsigner requirements.txt .

# Install Python dependencies (without pyHanko)
RUN pip install --no-cache-dir -r requirements.txt

# Copy Java signer JAR
COPY --chown=pdfsigner:pdfsigner java-signer/target/luxtrust-pdf-signer-1.0.0.jar /app/java-signer/

# Copy application code
COPY --chown=pdfsigner:pdfsigner . .

# Create directories for Gemalto library mount from host
RUN mkdir -p /usr/lib/pkcs11 /usr/lib/ClassicClient

# Set environment variables for Qt
ENV QT_QPA_PLATFORM=xcb
ENV XDG_RUNTIME_DIR=/tmp/runtime-pdfsigner
ENV DISPLAY=:0
ENV QT_DEBUG_PLUGINS=0

# Java settings
ENV JAVA_TOOL_OPTIONS="-Djava.security.egd=file:/dev/./urandom"

# Switch to non-root user
USER pdfsigner

# Create runtime directory
RUN mkdir -p /tmp/runtime-pdfsigner

CMD ["python", "main.py"]
