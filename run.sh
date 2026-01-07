#!/bin/bash
# Script to run PDF Signer with Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}PDF Signer LuxTrust - Docker Launcher${NC}"
echo "========================================"

# Check if pcscd is running on host
if ! pgrep -x "pcscd" > /dev/null; then
    echo -e "${YELLOW}Warning: pcscd is not running on host.${NC}"
    echo "Starting with embedded pcscd service..."
    COMPOSE_PROFILES="with-pcscd"
else
    echo -e "${GREEN}✓ pcscd detected on host${NC}"
    COMPOSE_PROFILES=""
fi

# Check for LuxTrust library
LUXTRUST_PATHS=(
    "/usr/lib/x86_64-linux-gnu/liblux_p11.so"
    "/usr/lib/liblux_p11.so"
    "/opt/LuxTrust/lib/liblux_p11.so"
)

LUXTRUST_FOUND=""
for path in "${LUXTRUST_PATHS[@]}"; do
    if [ -f "$path" ]; then
        LUXTRUST_FOUND="$path"
        echo -e "${GREEN}✓ LuxTrust library found: $path${NC}"
        break
    fi
done

if [ -z "$LUXTRUST_FOUND" ]; then
    echo -e "${RED}✗ LuxTrust middleware not found!${NC}"
    echo "Please install LuxTrust Middleware first."
    echo "Expected locations:"
    for path in "${LUXTRUST_PATHS[@]}"; do
        echo "  - $path"
    done
    exit 1
fi

# Allow X11 connections from local docker
echo -e "${GREEN}Configuring X11 access...${NC}"
xhost +local:docker 2>/dev/null || true

# Export display variables
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"

# Build and run
echo -e "${GREEN}Building and starting container...${NC}"

if [ -n "$COMPOSE_PROFILES" ]; then
    docker-compose --profile with-pcscd up --build
else
    docker-compose up --build
fi
