package lu.pdfsign;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.itextpdf.io.image.ImageData;
import com.itextpdf.io.image.ImageDataFactory;
import com.itextpdf.kernel.geom.Rectangle;
import com.itextpdf.kernel.pdf.PdfReader;
import com.itextpdf.kernel.pdf.StampingProperties;
import com.itextpdf.signatures.*;
import org.apache.commons.cli.*;
import org.bouncycastle.jce.provider.BouncyCastleProvider;

import java.io.*;
import java.io.PrintWriter;
import java.security.*;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.util.*;

/**
 * LuxTrust PDF Signer - Signs PDFs using Gemalto/LuxTrust PKCS#11 middleware
 */
public class LuxTrustSigner {

    private static final String DEFAULT_PKCS11_LIB = "/usr/lib/pkcs11/libgclib.so";
    private static final String[] PKCS11_PATHS = {
        "/usr/lib/pkcs11/libgclib.so",
        "/usr/lib/ClassicClient/libgclib.so",
        "/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so"
    };

    private final Gson gson = new GsonBuilder().setPrettyPrinting().create();
    private Provider pkcs11Provider;
    private KeyStore keyStore;

    public static void main(String[] args) {
        Security.addProvider(new BouncyCastleProvider());

        LuxTrustSigner signer = new LuxTrustSigner();

        try {
            signer.run(args);
        } catch (Exception e) {
            System.err.println(toJson("error", e.getMessage()));
            System.exit(1);
        }
    }

    public void run(String[] args) throws Exception {
        Options options = createOptions();
        CommandLineParser parser = new DefaultParser();

        try {
            CommandLine cmd = parser.parse(options, args);

            if (cmd.hasOption("help")) {
                printHelp(options);
                return;
            }

            if (cmd.hasOption("list-certs")) {
                listCertificates(cmd);
                return;
            }

            if (cmd.hasOption("sign")) {
                signPdf(cmd);
                return;
            }

            if (cmd.hasOption("list-tokens")) {
                listTokens(cmd);
                return;
            }

            printHelp(options);

        } catch (ParseException e) {
            System.err.println("Error: " + e.getMessage());
            printHelp(options);
            System.exit(1);
        }
    }

    private Options createOptions() {
        Options options = new Options();

        options.addOption("h", "help", false, "Afficher l'aide");
        options.addOption("l", "list-tokens", false, "Lister les tokens disponibles");
        options.addOption("c", "list-certs", false, "Lister les certificats");
        options.addOption("s", "sign", false, "Signer un PDF");

        options.addOption(Option.builder("p")
            .longOpt("pin")
            .hasArg()
            .desc("PIN du token")
            .build());

        options.addOption(Option.builder("i")
            .longOpt("input")
            .hasArg()
            .desc("Fichier PDF à signer")
            .build());

        options.addOption(Option.builder("o")
            .longOpt("output")
            .hasArg()
            .desc("Fichier PDF signé (sortie)")
            .build());

        options.addOption(Option.builder("a")
            .longOpt("alias")
            .hasArg()
            .desc("Alias du certificat à utiliser")
            .build());

        options.addOption(Option.builder()
            .longOpt("lib")
            .hasArg()
            .desc("Chemin vers la bibliothèque PKCS#11")
            .build());

        options.addOption(Option.builder()
            .longOpt("slot")
            .hasArg()
            .desc("Numéro du slot (défaut: 0)")
            .build());

        options.addOption(Option.builder()
            .longOpt("reason")
            .hasArg()
            .desc("Raison de la signature")
            .build());

        options.addOption(Option.builder()
            .longOpt("location")
            .hasArg()
            .desc("Lieu de la signature")
            .build());

        options.addOption(Option.builder()
            .longOpt("contact")
            .hasArg()
            .desc("Contact du signataire")
            .build());

        options.addOption(Option.builder()
            .longOpt("visible")
            .desc("Signature visible")
            .build());

        options.addOption(Option.builder()
            .longOpt("page")
            .hasArg()
            .desc("Numéro de page (défaut: 1)")
            .build());

        options.addOption(Option.builder()
            .longOpt("x")
            .hasArg()
            .desc("Position X de la signature")
            .build());

        options.addOption(Option.builder()
            .longOpt("y")
            .hasArg()
            .desc("Position Y de la signature")
            .build());

        options.addOption(Option.builder()
            .longOpt("width")
            .hasArg()
            .desc("Largeur de la signature")
            .build());

        options.addOption(Option.builder()
            .longOpt("height")
            .hasArg()
            .desc("Hauteur de la signature")
            .build());

        options.addOption(Option.builder()
            .longOpt("image")
            .hasArg()
            .desc("Chemin vers l'image de signature")
            .build());

        options.addOption(Option.builder()
            .longOpt("name")
            .hasArg()
            .desc("Nom du signataire")
            .build());

        options.addOption(Option.builder()
            .longOpt("json")
            .desc("Sortie en JSON")
            .build());

        return options;
    }

    private void printHelp(Options options) {
        HelpFormatter formatter = new HelpFormatter();
        formatter.printHelp("luxtrust-signer", options);
    }

    private String findPkcs11Library(CommandLine cmd) {
        if (cmd.hasOption("lib")) {
            return cmd.getOptionValue("lib");
        }

        for (String path : PKCS11_PATHS) {
            if (new File(path).exists()) {
                return path;
            }
        }

        return DEFAULT_PKCS11_LIB;
    }

    private void initPkcs11(String libPath, int slot, char[] pin) throws Exception {
        // Create temp config file for PKCS11
        File configFile = File.createTempFile("pkcs11", ".cfg");
        configFile.deleteOnExit();

        try (PrintWriter writer = new PrintWriter(configFile)) {
            writer.println("name = Gemalto");
            writer.println("library = " + libPath);
            writer.println("slotListIndex = " + slot);
        }

        try {
            pkcs11Provider = Security.getProvider("SunPKCS11");
            if (pkcs11Provider == null) {
                throw new RuntimeException("SunPKCS11 provider not available");
            }

            pkcs11Provider = pkcs11Provider.configure(configFile.getAbsolutePath());
            Security.addProvider(pkcs11Provider);

            keyStore = KeyStore.getInstance("PKCS11", pkcs11Provider);
            keyStore.load(null, pin);
        } catch (Exception e) {
            Throwable cause = e.getCause();
            String causeMsg = cause != null ? " caused by " + cause.getClass().getName() + ": " + cause.getMessage() : "";
            throw new RuntimeException("PKCS11 init error: " + e.getClass().getName() + ": " + e.getMessage() + causeMsg, e);
        }
    }

    private void listTokens(CommandLine cmd) throws Exception {
        String libPath = findPkcs11Library(cmd);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("library", libPath);
        result.put("exists", new File(libPath).exists());

        if (new File(libPath).exists()) {
            // Try to list slots
            List<Map<String, Object>> slots = new ArrayList<>();
            for (int i = 0; i < 4; i++) {
                try {
                    String config = String.format(
                        "--name = Test%d%n--library = %s%nslot = %d",
                        i, libPath, i
                    );
                    Provider p = Security.getProvider("SunPKCS11").configure(config);

                    Map<String, Object> slot = new LinkedHashMap<>();
                    slot.put("slot", i);
                    slot.put("available", true);
                    slots.add(slot);
                } catch (Exception e) {
                    // Slot not available
                }
            }
            result.put("slots", slots);
        }

        System.out.println(gson.toJson(result));
    }

    private void listCertificates(CommandLine cmd) throws Exception {
        String libPath = findPkcs11Library(cmd);
        int slot = Integer.parseInt(cmd.getOptionValue("slot", "0"));
        String pin = cmd.getOptionValue("pin");

        if (pin == null) {
            throw new IllegalArgumentException("PIN requis (-p/--pin)");
        }

        initPkcs11(libPath, slot, pin.toCharArray());

        List<Map<String, Object>> certs = new ArrayList<>();

        Enumeration<String> aliases = keyStore.aliases();
        while (aliases.hasMoreElements()) {
            String alias = aliases.nextElement();

            Map<String, Object> certInfo = new LinkedHashMap<>();
            certInfo.put("alias", alias);

            if (keyStore.isKeyEntry(alias)) {
                certInfo.put("hasPrivateKey", true);

                Certificate cert = keyStore.getCertificate(alias);
                if (cert instanceof X509Certificate) {
                    X509Certificate x509 = (X509Certificate) cert;
                    certInfo.put("subject", x509.getSubjectX500Principal().getName());
                    certInfo.put("issuer", x509.getIssuerX500Principal().getName());
                    certInfo.put("serial", x509.getSerialNumber().toString(16));
                    certInfo.put("notBefore", x509.getNotBefore().toString());
                    certInfo.put("notAfter", x509.getNotAfter().toString());

                    // Check key usage
                    boolean[] keyUsage = x509.getKeyUsage();
                    if (keyUsage != null) {
                        certInfo.put("digitalSignature", keyUsage[0]);
                        certInfo.put("nonRepudiation", keyUsage[1]);
                    }
                }
            } else {
                certInfo.put("hasPrivateKey", false);
            }

            certs.add(certInfo);
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("certificates", certs);
        result.put("count", certs.size());

        System.out.println(gson.toJson(result));
    }

    private void signPdf(CommandLine cmd) throws Exception {
        // Validate required parameters
        String inputFile = cmd.getOptionValue("input");
        String outputFile = cmd.getOptionValue("output");
        String pin = cmd.getOptionValue("pin");

        if (inputFile == null) {
            throw new IllegalArgumentException("Fichier d'entrée requis (-i/--input)");
        }
        if (outputFile == null) {
            throw new IllegalArgumentException("Fichier de sortie requis (-o/--output)");
        }
        if (pin == null) {
            throw new IllegalArgumentException("PIN requis (-p/--pin)");
        }

        // Initialize PKCS#11
        String libPath = findPkcs11Library(cmd);
        int slot = Integer.parseInt(cmd.getOptionValue("slot", "0"));
        initPkcs11(libPath, slot, pin.toCharArray());

        // Find signing certificate
        String alias = cmd.getOptionValue("alias");
        if (alias == null) {
            // Find first certificate with private key
            Enumeration<String> aliases = keyStore.aliases();
            while (aliases.hasMoreElements()) {
                String a = aliases.nextElement();
                if (keyStore.isKeyEntry(a)) {
                    Certificate cert = keyStore.getCertificate(a);
                    if (cert instanceof X509Certificate) {
                        X509Certificate x509 = (X509Certificate) cert;
                        boolean[] keyUsage = x509.getKeyUsage();
                        // Prefer non-repudiation certificate for signing
                        if (keyUsage != null && keyUsage[1]) {
                            alias = a;
                            break;
                        }
                        if (alias == null) {
                            alias = a;
                        }
                    }
                }
            }
        }

        if (alias == null) {
            throw new RuntimeException("Aucun certificat de signature trouvé");
        }

        // Get private key and certificate chain
        PrivateKey privateKey = (PrivateKey) keyStore.getKey(alias, null);
        Certificate[] chain = keyStore.getCertificateChain(alias);

        if (privateKey == null || chain == null) {
            throw new RuntimeException("Clé privée ou chaîne de certificats non trouvée pour: " + alias);
        }

        // Sign the PDF
        PdfReader reader = new PdfReader(inputFile);
        FileOutputStream fos = new FileOutputStream(outputFile);

        PdfSigner signer = new PdfSigner(reader, fos, new StampingProperties().useAppendMode());

        // Set signature appearance
        PdfSignatureAppearance appearance = signer.getSignatureAppearance();

        if (cmd.hasOption("reason")) {
            appearance.setReason(cmd.getOptionValue("reason"));
        }
        if (cmd.hasOption("location")) {
            appearance.setLocation(cmd.getOptionValue("location"));
        }
        if (cmd.hasOption("contact")) {
            appearance.setContact(cmd.getOptionValue("contact"));
        }

        // Visible signature
        if (cmd.hasOption("visible")) {
            int page = Integer.parseInt(cmd.getOptionValue("page", "1"));
            float x = Float.parseFloat(cmd.getOptionValue("x", "50"));
            float y = Float.parseFloat(cmd.getOptionValue("y", "50"));
            float width = Float.parseFloat(cmd.getOptionValue("width", "200"));
            float height = Float.parseFloat(cmd.getOptionValue("height", "50"));

            Rectangle rect = new Rectangle(x, y, width, height);
            appearance.setPageRect(rect);
            appearance.setPageNumber(page);

            // Set image as background (layer 0) if provided
            if (cmd.hasOption("image")) {
                String imagePath = cmd.getOptionValue("image");
                File imageFile = new File(imagePath);
                if (imageFile.exists()) {
                    ImageData imageData = ImageDataFactory.create(imagePath);
                    // Draw image on layer 0 (background) using PdfFormXObject
                    com.itextpdf.kernel.pdf.xobject.PdfFormXObject layer0 = appearance.getLayer0();
                    com.itextpdf.kernel.pdf.canvas.PdfCanvas canvas =
                        new com.itextpdf.kernel.pdf.canvas.PdfCanvas(layer0, signer.getDocument());
                    // Scale image to fit the signature rectangle
                    float imgWidth = imageData.getWidth();
                    float imgHeight = imageData.getHeight();
                    float scale = Math.min(width / imgWidth, height / imgHeight);
                    float scaledWidth = imgWidth * scale;
                    float scaledHeight = imgHeight * scale;
                    // Center the image
                    float xOffset = (width - scaledWidth) / 2;
                    float yOffset = (height - scaledHeight) / 2;
                    canvas.addImageFittedIntoRectangle(imageData,
                        new Rectangle(xOffset, yOffset, scaledWidth, scaledHeight), false);
                }
            }

            // Build layer 2 text (foreground)
            StringBuilder layer2Text = new StringBuilder();
            if (cmd.hasOption("name")) {
                layer2Text.append("Signé par: ").append(cmd.getOptionValue("name")).append("\n");
            }
            if (cmd.hasOption("reason")) {
                layer2Text.append("Raison: ").append(cmd.getOptionValue("reason")).append("\n");
            }
            if (cmd.hasOption("location")) {
                layer2Text.append("Lieu: ").append(cmd.getOptionValue("location")).append("\n");
            }
            layer2Text.append("Date: ").append(new java.text.SimpleDateFormat("dd/MM/yyyy HH:mm").format(new java.util.Date()));

            appearance.setLayer2Text(layer2Text.toString());
            appearance.setRenderingMode(PdfSignatureAppearance.RenderingMode.DESCRIPTION);
        }

        signer.setFieldName("Signature_LuxTrust");

        // Create signature
        IExternalSignature signature = new PrivateKeySignature(
            privateKey, DigestAlgorithms.SHA256, pkcs11Provider.getName()
        );
        IExternalDigest digest = new BouncyCastleDigest();

        signer.signDetached(digest, signature, chain, null, null, null, 0,
            PdfSigner.CryptoStandard.CADES);

        // Output result
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("success", true);
        result.put("input", inputFile);
        result.put("output", outputFile);
        result.put("certificate", alias);

        X509Certificate x509 = (X509Certificate) chain[0];
        result.put("signer", x509.getSubjectX500Principal().getName());

        System.out.println(gson.toJson(result));
    }

    private static String toJson(String key, Object value) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put(key, value);
        return new Gson().toJson(map);
    }
}
