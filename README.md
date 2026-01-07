# PDF Signer LuxTrust

Application de signature de documents PDF avec cartes a puce LuxTrust.

## Fonctionnalites

- Signature numerique de PDF avec certificats LuxTrust
- Interface graphique Qt (PySide6)
- Support des signatures visibles avec image personnalisee
- Detection des signatures existantes a l'ouverture d'un document
- Persistence de la configuration de signature

## Prerequis

### Systeme
- Ubuntu/Debian Linux (64-bit)
- Java 8 ou superieur
- Python 3.10+

### Middleware LuxTrust
Installer le middleware Gemalto/Thales pour les cartes LuxTrust:

```bash
# Telecharger depuis le site LuxTrust ou utiliser le package fourni
sudo dpkg -i Gemalto_Middleware_Ubuntu_64bit_7.5.0-b02.00.deb
sudo apt-get install -f  # Installer les dependances manquantes
```

La bibliotheque PKCS#11 sera installee dans `/usr/lib/pkcs11/libgclib.so`.

### Dependances Python
```bash
pip install -r requirements.txt
```

## Installation

```bash
git clone https://github.com/ceeeeb/pdfsignluxtrust.git
cd pdfsignluxtrust

# Installer les dependances Python
pip install -r requirements.txt

# Compiler le signer Java
cd java-signer
mvn clean package
cd ..
```

## Utilisation

### Interface graphique
```bash
python3 main.py
```

1. Ouvrir un document PDF
2. Placer le rectangle de signature sur le document
3. Configurer l'apparence (nom, raison, image)
4. Cliquer "Signer le document"
5. Entrer le PIN de la carte LuxTrust

### Ligne de commande (Java)
```bash
# Lister les certificats
java -jar java-signer/target/luxtrust-pdf-signer-1.0.0.jar \
  --list-certs --pin VOTRE_PIN --lib /usr/lib/pkcs11/libgclib.so

# Signer un PDF
java -jar java-signer/target/luxtrust-pdf-signer-1.0.0.jar \
  --sign \
  --input document.pdf \
  --output document_signe.pdf \
  --pin VOTRE_PIN \
  --lib /usr/lib/pkcs11/libgclib.so \
  --visible \
  --name "Votre Nom" \
  --reason "Approbation" \
  --image /chemin/vers/signature.png
```

## Configuration

La configuration de signature est sauvegardee dans:
```
~/.config/pdfsign-luxtrust/settings.json
```

## Structure du projet

```
pdfsignluxtrust/
├── main.py                 # Point d'entree
├── pdfsign/
│   ├── core/
│   │   ├── pdf_document.py     # Wrapper PyMuPDF
│   │   └── signature_manager.py # Gestionnaire de signatures
│   ├── crypto/
│   │   ├── java_signer.py      # Interface Python vers Java
│   │   └── pkcs11_manager.py   # Gestion PKCS#11
│   ├── ui/
│   │   ├── main_window.py      # Fenetre principale
│   │   ├── pdf_viewer.py       # Visualiseur PDF
│   │   └── dialogs/            # Dialogues
│   └── utils/
│       ├── platform.py         # Detection plateforme
│       └── settings.py         # Persistence configuration
└── java-signer/
    └── src/main/java/lu/pdfsign/
        └── LuxTrustSigner.java # Signer Java avec iText 7
```

## Soutenir le projet

Si cette application vous est utile, vous pouvez soutenir son developpement:

[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub-pink?logo=github)](https://github.com/sponsors/ceeeeb)

## Licence

MIT License
