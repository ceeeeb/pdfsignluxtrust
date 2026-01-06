"""PKCS#11 token management for LuxTrust and other tokens."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID

from pdfsign.utils.platform import discover_pkcs11_library, validate_pkcs11_library


@dataclass
class TokenInfo:
    """Information about a PKCS#11 token."""
    slot_id: int
    label: str
    manufacturer: str
    model: str
    serial: str


@dataclass
class CertificateInfo:
    """Information about a certificate on the token."""
    label: str
    subject_cn: str
    issuer_cn: str
    serial_number: str
    not_before: str
    not_after: str
    key_id: bytes
    can_sign: bool


class PKCS11Error(Exception):
    """Exception for PKCS#11 related errors."""
    pass


class PKCS11Manager:
    """
    Manager for PKCS#11 token operations.

    Uses pyHanko's PKCS#11 support for cryptographic operations.
    """

    def __init__(self, lib_path: Path | str | None = None):
        """
        Initialize the PKCS#11 manager.

        Args:
            lib_path: Path to PKCS#11 library. Auto-detected if None.

        Raises:
            PKCS11Error: If library cannot be found or loaded.
        """
        self._lib_path: Path | None = None
        self._session = None
        self._pkcs11_lib = None

        if lib_path:
            path = Path(lib_path)
            if not validate_pkcs11_library(path):
                raise PKCS11Error(f"Invalid PKCS#11 library: {path}")
            self._lib_path = path
        else:
            self._lib_path = discover_pkcs11_library()
            if not self._lib_path:
                raise PKCS11Error(
                    "PKCS#11 library not found. "
                    "Please install LuxTrust Middleware or specify library path."
                )

    @property
    def library_path(self) -> Path | None:
        """Get the PKCS#11 library path."""
        return self._lib_path

    @property
    def is_session_open(self) -> bool:
        """Check if a session is currently open."""
        return self._session is not None

    def list_tokens(self) -> list[TokenInfo]:
        """
        List all available PKCS#11 tokens.

        Returns:
            List of TokenInfo for each detected token.

        Raises:
            PKCS11Error: If tokens cannot be enumerated.
        """
        try:
            from pkcs11 import lib as pkcs11_lib
            from pkcs11.exceptions import PKCS11Error as PKCSError

            lib = pkcs11_lib(str(self._lib_path))
            tokens = []

            for slot in lib.get_slots(token_present=True):
                token = slot.get_token()
                tokens.append(TokenInfo(
                    slot_id=slot.slot_id,
                    label=token.label.strip(),
                    manufacturer=token.manufacturer_id.strip(),
                    model=token.model.strip(),
                    serial=token.serial_number.strip(),
                ))

            return tokens

        except ImportError:
            raise PKCS11Error("python-pkcs11 not installed")
        except PKCSError as e:
            raise PKCS11Error(f"Failed to enumerate tokens: {e}") from e
        except Exception as e:
            raise PKCS11Error(f"Unexpected error listing tokens: {e}") from e

    def list_certificates(self, slot_id: int, pin: str) -> list[CertificateInfo]:
        """
        List certificates on a specific token.

        Args:
            slot_id: PKCS#11 slot ID.
            pin: User PIN for the token.

        Returns:
            List of CertificateInfo for signing certificates.

        Raises:
            PKCS11Error: If certificates cannot be read.
        """
        try:
            from pkcs11 import lib as pkcs11_lib, ObjectClass, Attribute
            from pkcs11.exceptions import PKCS11Error as PKCSError

            lib = pkcs11_lib(str(self._lib_path))
            slot = None

            for s in lib.get_slots(token_present=True):
                if s.slot_id == slot_id:
                    slot = s
                    break

            if not slot:
                raise PKCS11Error(f"Slot {slot_id} not found")

            certs = []
            with slot.get_token().open(user_pin=pin) as session:
                # Find all certificates
                for obj in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
                    try:
                        cert_der = obj[Attribute.VALUE]
                        cert = x509.load_der_x509_certificate(cert_der)

                        # Get common names
                        subject_cn = self._get_cn(cert.subject)
                        issuer_cn = self._get_cn(cert.issuer)

                        # Check if corresponding private key exists (for signing)
                        key_id = obj.get(Attribute.ID, b"")
                        can_sign = self._has_private_key(session, key_id)

                        certs.append(CertificateInfo(
                            label=obj.get(Attribute.LABEL, "").strip(),
                            subject_cn=subject_cn,
                            issuer_cn=issuer_cn,
                            serial_number=format(cert.serial_number, "x"),
                            not_before=cert.not_valid_before_utc.isoformat(),
                            not_after=cert.not_valid_after_utc.isoformat(),
                            key_id=key_id,
                            can_sign=can_sign,
                        ))
                    except Exception:
                        continue  # Skip malformed certificates

            # Filter to only signing certificates
            return [c for c in certs if c.can_sign]

        except ImportError:
            raise PKCS11Error("python-pkcs11 not installed")
        except PKCSError as e:
            error_msg = str(e).lower()
            if "pin" in error_msg:
                raise PKCS11Error("Invalid PIN") from e
            raise PKCS11Error(f"Failed to list certificates: {e}") from e
        except Exception as e:
            raise PKCS11Error(f"Unexpected error: {e}") from e

    def _get_cn(self, name: x509.Name) -> str:
        """Extract Common Name from X.509 name."""
        try:
            cn_attr = name.get_attributes_for_oid(NameOID.COMMON_NAME)
            if cn_attr:
                return cn_attr[0].value
        except Exception:
            pass
        return str(name)

    def _has_private_key(self, session, key_id: bytes) -> bool:
        """Check if a private key with the given ID exists."""
        try:
            from pkcs11 import ObjectClass, Attribute

            for _ in session.get_objects({
                Attribute.CLASS: ObjectClass.PRIVATE_KEY,
                Attribute.ID: key_id,
            }):
                return True
        except Exception:
            pass
        return False

    def create_signer(
        self,
        slot_id: int,
        key_label: str | None = None,
        key_id: bytes | None = None,
    ):
        """
        Create a pyHanko PKCS11Signer.

        Args:
            slot_id: PKCS#11 slot ID.
            key_label: Label of the key to use (optional).
            key_id: ID of the key to use (optional).

        Returns:
            PKCS11Signer instance for use with pyHanko.

        Note:
            PIN will be requested by pyHanko during signing.
        """
        from pyhanko.sign.pkcs11 import PKCS11Signer

        return PKCS11Signer(
            lib_location=str(self._lib_path),
            slot_no=slot_id,
            key_label=key_label,
            key_id=key_id,
        )

    def create_signer_with_pin(
        self,
        slot_id: int,
        pin: str,
        cert_label: str | None = None,
        key_id: bytes | None = None,
    ):
        """
        Create a pyHanko PKCS11Signer with PIN already set.

        Args:
            slot_id: PKCS#11 slot ID.
            pin: User PIN.
            cert_label: Label of the certificate to use.
            key_id: ID of the key to use.

        Returns:
            PKCS11Signer instance configured with PIN.
        """
        from pyhanko.sign.pkcs11 import PKCS11Signer

        return PKCS11Signer(
            lib_location=str(self._lib_path),
            slot_no=slot_id,
            user_pin=pin,
            cert_label=cert_label,
            key_id=key_id,
        )

    def test_pin(self, slot_id: int, pin: str) -> bool:
        """
        Test if a PIN is valid for a token.

        Args:
            slot_id: PKCS#11 slot ID.
            pin: PIN to test.

        Returns:
            True if PIN is valid, False otherwise.
        """
        try:
            from pkcs11 import lib as pkcs11_lib
            from pkcs11.exceptions import PKCS11Error as PKCSError

            lib = pkcs11_lib(str(self._lib_path))

            for slot in lib.get_slots(token_present=True):
                if slot.slot_id == slot_id:
                    with slot.get_token().open(user_pin=pin):
                        return True

            return False

        except PKCSError:
            return False
        except Exception:
            return False
