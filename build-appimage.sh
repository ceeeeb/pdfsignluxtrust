#!/bin/bash
# Build script for PDF Signer LuxTrust AppImage
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
APPDIR="$BUILD_DIR/PDFSignLuxTrust.AppDir"
JRE_VERSION="21.0.5+11"
JRE_DIR="$BUILD_DIR/jre"

echo "=== PDF Signer LuxTrust AppImage Builder ==="

# Check dependencies
check_dependencies() {
    echo "Checking dependencies..."

    if ! command -v python3 &> /dev/null; then
        echo "Error: python3 is required"
        exit 1
    fi

    if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
        echo "Error: pip is required"
        exit 1
    fi

    if ! command -v mvn &> /dev/null; then
        echo "Warning: Maven not found, Java JAR must already be built"
    fi
}

# Download and extract JRE
download_jre() {
    if [ -d "$JRE_DIR" ]; then
        echo "JRE already downloaded"
        return
    fi

    echo "Downloading Eclipse Temurin JRE $JRE_VERSION..."
    mkdir -p "$BUILD_DIR"

    JRE_URL="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.5%2B11/OpenJDK21U-jre_x64_linux_hotspot_21.0.5_11.tar.gz"
    JRE_TAR="$BUILD_DIR/jre.tar.gz"

    curl -L -o "$JRE_TAR" "$JRE_URL"

    echo "Extracting JRE..."
    mkdir -p "$JRE_DIR"
    tar -xzf "$JRE_TAR" -C "$JRE_DIR" --strip-components=1
    rm "$JRE_TAR"

    echo "JRE downloaded to $JRE_DIR"
}

# Build Java signer
build_java() {
    JAR_PATH="$SCRIPT_DIR/java-signer/target/luxtrust-pdf-signer-1.0.0.jar"

    if [ -f "$JAR_PATH" ]; then
        echo "Java JAR already built"
        return
    fi

    if ! command -v mvn &> /dev/null; then
        echo "Error: Maven required to build Java signer"
        exit 1
    fi

    echo "Building Java signer..."
    cd "$SCRIPT_DIR/java-signer"
    mvn clean package -q
    cd "$SCRIPT_DIR"

    echo "Java signer built"
}

# Build with PyInstaller
build_pyinstaller() {
    echo "Installing Python dependencies..."
    pip3 install --user -q pyinstaller
    pip3 install --user -q -r "$SCRIPT_DIR/requirements.txt"

    echo "Running PyInstaller..."
    cd "$SCRIPT_DIR"
    python3 -m PyInstaller --clean --noconfirm pdfsign.spec

    echo "PyInstaller build complete"
}

# Create AppDir structure
create_appdir() {
    echo "Creating AppDir structure..."

    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/lib"
    mkdir -p "$APPDIR/usr/share/java"
    mkdir -p "$APPDIR/usr/share/jre"

    # Copy PyInstaller output
    cp -r "$SCRIPT_DIR/dist/pdfsign/"* "$APPDIR/usr/bin/"

    # Copy Java JAR
    cp "$SCRIPT_DIR/java-signer/target/luxtrust-pdf-signer-1.0.0.jar" "$APPDIR/usr/share/java/"

    # Copy JRE
    cp -r "$JRE_DIR/"* "$APPDIR/usr/share/jre/"

    # Copy desktop file and icon
    cp "$SCRIPT_DIR/appimage/pdfsign.desktop" "$APPDIR/"
    cp "$SCRIPT_DIR/appimage/pdfsign.svg" "$APPDIR/"

    # Create AppRun script
    cat > "$APPDIR/AppRun" << 'APPRUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}

# Set up environment
export PATH="$HERE/usr/bin:$HERE/usr/share/jre/bin:$PATH"
export JAVA_HOME="$HERE/usr/share/jre"

# Preserve host system library paths for PKCS#11 middleware (Gemalto)
HOST_LIB_PATHS="/usr/lib/pkcs11:/usr/lib/ClassicClient:/usr/lib/x86_64-linux-gnu:/usr/lib"
export LD_LIBRARY_PATH="$HERE/usr/lib:$HOST_LIB_PATHS:$LD_LIBRARY_PATH"

# Auto-detect PKCS#11 library on host system
for PKCS11_PATH in /usr/lib/pkcs11/libgclib.so /usr/lib/ClassicClient/libgclib.so /usr/lib/x86_64-linux-gnu/opensc-pkcs11.so; do
    if [ -f "$PKCS11_PATH" ]; then
        export PDFSIGN_PKCS11_LIB="$PKCS11_PATH"
        break
    fi
done

# AppImage paths for the application
export PDFSIGN_JAR_PATH="$HERE/usr/share/java/luxtrust-pdf-signer-1.0.0.jar"
export PDFSIGN_JAVA_HOME="$HERE/usr/share/jre"

# Run the application
exec "$HERE/usr/bin/pdfsign" "$@"
APPRUN

    chmod +x "$APPDIR/AppRun"

    echo "AppDir created at $APPDIR"
}

# Download appimagetool and build AppImage
build_appimage() {
    echo "Downloading appimagetool..."

    APPIMAGETOOL="$BUILD_DIR/appimagetool-x86_64.AppImage"

    if [ ! -f "$APPIMAGETOOL" ]; then
        curl -L -o "$APPIMAGETOOL" "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
        chmod +x "$APPIMAGETOOL"
    fi

    echo "Building AppImage..."
    cd "$BUILD_DIR"

    export ARCH=x86_64

    # Try to run appimagetool
    if [ -n "$APPIMAGE_EXTRACT_AND_RUN" ] || ! "$APPIMAGETOOL" --version &> /dev/null; then
        # Extract and run if FUSE not available
        "$APPIMAGETOOL" --appimage-extract &> /dev/null || true
        ./squashfs-root/AppRun "$APPDIR" "PDFSignLuxTrust-x86_64.AppImage"
        rm -rf squashfs-root
    else
        "$APPIMAGETOOL" "$APPDIR" "PDFSignLuxTrust-x86_64.AppImage"
    fi

    mv "PDFSignLuxTrust-x86_64.AppImage" "$SCRIPT_DIR/"

    echo ""
    echo "=== Build Complete ==="
    echo "AppImage created: $SCRIPT_DIR/PDFSignLuxTrust-x86_64.AppImage"
    echo ""
    echo "Note: The PKCS#11 middleware (Gemalto) must be installed on the target system:"
    echo "  sudo dpkg -i Gemalto_Middleware_Ubuntu_64bit_7.5.0-b02.00.deb"
}

# Clean build artifacts
clean() {
    echo "Cleaning build artifacts..."
    rm -rf "$BUILD_DIR"
    rm -rf "$SCRIPT_DIR/dist"
    rm -rf "$SCRIPT_DIR/build"
    rm -f "$SCRIPT_DIR/PDFSignLuxTrust-x86_64.AppImage"
    echo "Clean complete"
}

# Main
case "${1:-build}" in
    clean)
        clean
        ;;
    build|*)
        check_dependencies
        download_jre
        build_java
        build_pyinstaller
        create_appdir
        build_appimage
        ;;
esac
