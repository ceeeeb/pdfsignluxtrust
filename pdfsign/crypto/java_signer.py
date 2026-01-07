"""Java-based PDF signer using LuxTrust/Gemalto PKCS#11."""

import json
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CertificateInfo:
    """Information about a certificate on the token."""
    alias: str
    subject: str
    issuer: str
    serial: str
    not_before: str
    not_after: str
    has_private_key: bool
    can_sign: bool


@dataclass
class SignatureResult:
    """Result of a signing operation."""
    success: bool
    input_file: str
    output_file: str
    certificate: str
    signer: str
    error: Optional[str] = None


class JavaSignerError(Exception):
    """Exception for Java signer related errors."""
    pass


class JavaSigner:
    """
    PDF Signer using Java and Gemalto/LuxTrust PKCS#11.

    This class wraps the Java-based signer tool to provide
    PDF signing capabilities with LuxTrust smart cards.
    """

    # Default paths for the JAR and PKCS#11 library
    DEFAULT_JAR_PATHS = [
        Path(__file__).parent.parent.parent / "java-signer" / "target" / "luxtrust-pdf-signer-1.0.0.jar",
        Path("/app/java-signer/luxtrust-pdf-signer-1.0.0.jar"),
        Path("/opt/luxtrust-signer/luxtrust-pdf-signer-1.0.0.jar"),
    ]

    DEFAULT_PKCS11_PATHS = [
        "/usr/lib/pkcs11/libgclib.so",
        "/usr/lib/ClassicClient/libgclib.so",
        "/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so",
    ]

    def __init__(
        self,
        jar_path: Optional[Path] = None,
        pkcs11_lib: Optional[str] = None,
        java_home: Optional[str] = None,
    ):
        """
        Initialize the Java signer.

        Args:
            jar_path: Path to the signer JAR file.
            pkcs11_lib: Path to PKCS#11 library.
            java_home: Java home directory.
        """
        self._jar_path = jar_path or self._find_jar()
        self._pkcs11_lib = pkcs11_lib or self._find_pkcs11_lib()
        self._java_cmd = self._find_java(java_home)

        if not self._jar_path or not self._jar_path.exists():
            raise JavaSignerError(f"JAR not found: {self._jar_path}")

    def _find_jar(self) -> Optional[Path]:
        """Find the signer JAR file."""
        for path in self.DEFAULT_JAR_PATHS:
            if path.exists():
                return path
        return None

    def _find_pkcs11_lib(self) -> Optional[str]:
        """Find the PKCS#11 library."""
        for path in self.DEFAULT_PKCS11_PATHS:
            if Path(path).exists():
                return path
        return None

    def _find_java(self, java_home: Optional[str]) -> str:
        """Find the Java executable."""
        if java_home:
            java_cmd = Path(java_home) / "bin" / "java"
            if java_cmd.exists():
                return str(java_cmd)

        # Try to find java in PATH
        java_cmd = shutil.which("java")
        if java_cmd:
            return java_cmd

        raise JavaSignerError("Java not found")

    def _run_command(self, args: list) -> dict:
        """Run a Java command and return JSON result."""
        cmd = [self._java_cmd, "-jar", str(self._jar_path)] + args

        if self._pkcs11_lib:
            cmd.extend(["--lib", self._pkcs11_lib])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Parse JSON output
            output = result.stdout.strip()
            if output:
                return json.loads(output)

            if result.returncode != 0:
                error = result.stderr.strip() or "Unknown error"
                raise JavaSignerError(error)

            return {}

        except subprocess.TimeoutExpired:
            raise JavaSignerError("Command timed out")
        except json.JSONDecodeError as e:
            raise JavaSignerError(f"Invalid JSON response: {e}")

    def list_certificates(self, pin: str, slot: int = 0) -> list[CertificateInfo]:
        """
        List certificates on the token.

        Args:
            pin: User PIN for the token.
            slot: PKCS#11 slot number.

        Returns:
            List of CertificateInfo objects.
        """
        result = self._run_command([
            "--list-certs",
            "--pin", pin,
            "--slot", str(slot),
        ])

        certs = []
        for cert_data in result.get("certificates", []):
            certs.append(CertificateInfo(
                alias=cert_data.get("alias", ""),
                subject=cert_data.get("subject", ""),
                issuer=cert_data.get("issuer", ""),
                serial=cert_data.get("serial", ""),
                not_before=cert_data.get("notBefore", ""),
                not_after=cert_data.get("notAfter", ""),
                has_private_key=cert_data.get("hasPrivateKey", False),
                can_sign=cert_data.get("digitalSignature", False) or cert_data.get("nonRepudiation", False),
            ))

        return certs

    def sign_pdf(
        self,
        input_path: Path,
        output_path: Path,
        pin: str,
        alias: Optional[str] = None,
        slot: int = 0,
        reason: str = "",
        location: str = "",
        contact: str = "",
        name: str = "",
        image_path: Optional[str] = None,
        visible: bool = False,
        page: int = 1,
        x: float = 50,
        y: float = 50,
        width: float = 200,
        height: float = 50,
    ) -> SignatureResult:
        """
        Sign a PDF document.

        Args:
            input_path: Path to input PDF.
            output_path: Path for signed PDF.
            pin: User PIN.
            alias: Certificate alias (auto-detected if None).
            slot: PKCS#11 slot number.
            reason: Signing reason.
            location: Signing location.
            contact: Signer contact info.
            name: Signer name for display.
            image_path: Path to signature image.
            visible: Whether signature should be visible.
            page: Page number for visible signature.
            x, y: Position of visible signature.
            width, height: Size of visible signature.

        Returns:
            SignatureResult with operation status.
        """
        args = [
            "--sign",
            "--input", str(input_path),
            "--output", str(output_path),
            "--pin", pin,
            "--slot", str(slot),
        ]

        if alias:
            args.extend(["--alias", alias])
        if reason:
            args.extend(["--reason", reason])
        if location:
            args.extend(["--location", location])
        if contact:
            args.extend(["--contact", contact])
        if name:
            args.extend(["--name", name])
        if image_path and Path(image_path).exists():
            args.extend(["--image", str(image_path)])

        if visible:
            args.append("--visible")
            args.extend(["--page", str(page)])
            args.extend(["--x", str(x)])
            args.extend(["--y", str(y)])
            args.extend(["--width", str(width)])
            args.extend(["--height", str(height)])

        try:
            result = self._run_command(args)

            return SignatureResult(
                success=result.get("success", False),
                input_file=result.get("input", str(input_path)),
                output_file=result.get("output", str(output_path)),
                certificate=result.get("certificate", ""),
                signer=result.get("signer", ""),
            )
        except JavaSignerError as e:
            return SignatureResult(
                success=False,
                input_file=str(input_path),
                output_file=str(output_path),
                certificate="",
                signer="",
                error=str(e),
            )

    def test_connection(self, pin: str, slot: int = 0) -> bool:
        """
        Test if the token is accessible.

        Args:
            pin: User PIN.
            slot: PKCS#11 slot number.

        Returns:
            True if connection successful.
        """
        try:
            certs = self.list_certificates(pin, slot)
            return len(certs) > 0
        except JavaSignerError:
            return False
