#!/bin/bash
#
# PDF Signer LuxTrust - Script de lancement
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAR_FILE="$SCRIPT_DIR/java-signer/target/luxtrust-pdf-signer-1.0.0.jar"
PKCS11_LIB="/usr/lib/pkcs11/libgclib.so"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "==================================="
echo "  PDF Signer LuxTrust"
echo "==================================="
echo

# Verifier Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERREUR]${NC} Python 3 n'est pas installe"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Python 3 trouve"

# Verifier Java
if ! command -v java &> /dev/null; then
    echo -e "${RED}[ERREUR]${NC} Java n'est pas installe"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Java trouve"

# Verifier le middleware PKCS#11
if [ -f "$PKCS11_LIB" ]; then
    echo -e "${GREEN}[OK]${NC} Middleware LuxTrust trouve"
else
    echo -e "${YELLOW}[ATTENTION]${NC} Middleware LuxTrust non trouve ($PKCS11_LIB)"
    echo "    Installez le middleware Gemalto pour utiliser les cartes LuxTrust"
fi

# Compiler le JAR si necessaire
if [ ! -f "$JAR_FILE" ]; then
    echo
    echo "Compilation du signer Java..."
    if command -v mvn &> /dev/null; then
        cd "$SCRIPT_DIR/java-signer"
        mvn clean package -q
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}[OK]${NC} JAR compile"
        else
            echo -e "${RED}[ERREUR]${NC} Echec de la compilation"
            exit 1
        fi
        cd "$SCRIPT_DIR"
    else
        echo -e "${RED}[ERREUR]${NC} Maven n'est pas installe (necessaire pour compiler)"
        exit 1
    fi
else
    echo -e "${GREEN}[OK]${NC} JAR trouve"
fi

# Verifier les dependances Python
echo
echo "Verification des dependances Python..."
python3 -c "import PySide6; import pymupdf" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}[INFO]${NC} Installation des dependances..."
    pip install -r "$SCRIPT_DIR/requirements.txt" -q
fi
echo -e "${GREEN}[OK]${NC} Dependances Python"

# Lancer l'application
echo
echo "Lancement de l'application..."
echo
cd "$SCRIPT_DIR"
python3 main.py "$@"
