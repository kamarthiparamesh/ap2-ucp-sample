"""
Utility functions for payment processing, encryption, and WebAuthn verification.
"""

import base64
import hashlib
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, ec
from cryptography.hazmat.backends import default_backend
import os


class CardEncryption:
    """Handle card number encryption and decryption."""

    def __init__(self):
        # In production, store this in a secure key management service (KMS)
        encryption_key = os.getenv("CARD_ENCRYPTION_KEY")
        if not encryption_key:
            # Generate a key if none exists (for development only)
            encryption_key = Fernet.generate_key().decode()
            print(f"WARNING: Generated new encryption key. Set CARD_ENCRYPTION_KEY={encryption_key}")

        self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

    def encrypt_card_number(self, card_number: str) -> str:
        """Encrypt card number for storage."""
        # Remove spaces and hyphens
        clean_number = card_number.replace(" ", "").replace("-", "")
        encrypted = self.cipher.encrypt(clean_number.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_card_number(self, encrypted_card: str) -> str:
        """Decrypt card number from storage."""
        encrypted_bytes = base64.b64decode(encrypted_card.encode())
        decrypted = self.cipher.decrypt(encrypted_bytes)
        return decrypted.decode()

    @staticmethod
    def get_last_four(card_number: str) -> str:
        """Extract last 4 digits from card number."""
        clean_number = card_number.replace(" ", "").replace("-", "")
        return clean_number[-4:]

    @staticmethod
    def detect_card_network(card_number: str) -> str:
        """Detect card network from card number."""
        clean_number = card_number.replace(" ", "").replace("-", "")

        # Mastercard: starts with 51-55 or 2221-2720
        if clean_number[0] == '5' and clean_number[1] in '12345':
            return "mastercard"
        if clean_number[:4].isdigit() and 2221 <= int(clean_number[:4]) <= 2720:
            return "mastercard"

        # Visa: starts with 4
        if clean_number[0] == '4':
            return "visa"

        # Amex: starts with 34 or 37
        if clean_number[:2] in ['34', '37']:
            return "amex"

        # Discover: starts with 6011, 622126-622925, 644-649, or 65
        if clean_number[:4] == '6011' or clean_number[:2] == '65':
            return "discover"
        if clean_number[:6].isdigit() and 622126 <= int(clean_number[:6]) <= 622925:
            return "discover"
        if clean_number[:3].isdigit() and 644 <= int(clean_number[:3]) <= 649:
            return "discover"

        return "unknown"


class WebAuthnVerifier:
    """Handle WebAuthn credential verification."""

    @staticmethod
    def generate_challenge(length: int = 32) -> str:
        """Generate a random challenge for WebAuthn."""
        random_bytes = os.urandom(length)
        return base64.urlsafe_b64encode(random_bytes).decode('utf-8').rstrip('=')

    @staticmethod
    def verify_registration(
        client_data_json: str,
        attestation_object: str,
        challenge: str,
        credential_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify WebAuthn registration response.

        Returns: {
            "credential_id": str,
            "public_key": str,
            "valid": bool
        }
        """
        try:
            # Decode client data
            client_data = json.loads(base64.urlsafe_b64decode(client_data_json + '=='))

            # Verify challenge matches
            received_challenge = client_data.get('challenge', '')
            if received_challenge != challenge:
                return {"valid": False, "error": "Challenge mismatch"}

            # Verify origin (in production, check against allowed origins)
            origin = client_data.get('origin', '')
            # For development, allow localhost
            if not (origin.startswith('http://localhost') or origin.startswith('https://')):
                return {"valid": False, "error": "Invalid origin"}

            # Decode attestation object (simplified - in production use full CBOR parsing)
            # For demo purposes, we'll extract the basic info
            attestation_data = base64.urlsafe_b64decode(attestation_object + '==')

            # In a real implementation, you would:
            # 1. Parse CBOR attestation object
            # 2. Extract authenticator data
            # 3. Verify attestation signature
            # 4. Extract credential ID and public key

            # Use the credential_id provided from the frontend (from browser's WebAuthn API)
            # If not provided, fall back to generating one (for backward compatibility)
            if not credential_id:
                credential_id = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')

            # In production, extract actual public key from attestation
            # For demo, generate a placeholder
            public_key = base64.b64encode(os.urandom(64)).decode('utf-8')

            return {
                "valid": True,
                "credential_id": credential_id,
                "public_key": public_key
            }

        except Exception as e:
            return {"valid": False, "error": str(e)}

    @staticmethod
    def verify_authentication(
        credential_id: str,
        client_data_json: str,
        authenticator_data: str,
        signature: str,
        public_key: str,
        challenge: str
    ) -> bool:
        """
        Verify WebAuthn authentication response.

        In production, this would:
        1. Verify client data JSON contains correct challenge
        2. Verify authenticator data flags
        3. Verify signature using stored public key
        4. Verify counter to prevent replay attacks

        For demo purposes, we do simplified verification.
        """
        try:
            # Decode and verify client data
            client_data = json.loads(base64.urlsafe_b64decode(client_data_json + '=='))

            # Verify challenge
            if client_data.get('challenge', '') != challenge:
                return False

            # Verify origin
            origin = client_data.get('origin', '')
            if not (origin.startswith('http://localhost') or origin.startswith('https://')):
                return False

            # In production, verify signature using public_key
            # For demo, accept if all data is present
            if credential_id and authenticator_data and signature and public_key:
                return True

            return False

        except Exception as e:
            print(f"WebAuthn verification error: {e}")
            return False


class PaymentTokenGenerator:
    """Generate secure payment tokens for AP2 protocol."""

    @staticmethod
    def generate_payment_token(user_email: str, card_id: str) -> str:
        """Generate a secure, opaque payment token."""
        # Combine user info with random data
        token_data = f"{user_email}:{card_id}:{uuid.uuid4().hex}"

        # Hash to create opaque token
        token_hash = hashlib.sha256(token_data.encode()).hexdigest()

        # Return shortened, URL-safe token
        return base64.urlsafe_b64encode(token_hash.encode()[:32]).decode('utf-8').rstrip('=')

    @staticmethod
    def generate_mandate_id() -> str:
        """Generate unique payment mandate ID."""
        return f"PM-{uuid.uuid4().hex[:16].upper()}"

    @staticmethod
    def generate_confirmation_id() -> str:
        """Generate unique confirmation ID for receipts."""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        random_part = uuid.uuid4().hex[:8].upper()
        return f"CONF-{timestamp}-{random_part}"


class OTPManager:
    """Manage OTP challenges for payment verification."""

    def __init__(self):
        self.challenges: Dict[str, Dict[str, Any]] = {}

    def generate_otp(self, mandate_id: str, length: int = 6) -> str:
        """Generate OTP for payment mandate."""
        # Generate random numeric OTP
        otp = ''.join([str(ord(c) % 10) for c in os.urandom(length)])

        # Store with expiry
        self.challenges[mandate_id] = {
            "otp": otp,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=5),
            "attempts": 0
        }

        return otp

    def verify_otp(self, mandate_id: str, user_otp: str) -> bool:
        """Verify OTP for payment mandate."""
        challenge = self.challenges.get(mandate_id)

        if not challenge:
            return False

        # Check expiry
        if datetime.utcnow() > challenge["expires_at"]:
            del self.challenges[mandate_id]
            return False

        # Check attempts
        if challenge["attempts"] >= 3:
            del self.challenges[mandate_id]
            return False

        # Increment attempts
        challenge["attempts"] += 1

        # Verify OTP
        if challenge["otp"] == user_otp:
            # Success - remove challenge
            del self.challenges[mandate_id]
            return True

        return False

    def send_otp(self, mandate_id: str, user_email: str, otp: str):
        """
        Send OTP to user via email/SMS.
        In production, integrate with email/SMS service.
        For demo, just log it.
        """
        print(f"[OTP] Sending OTP to {user_email}: {otp} (Mandate: {mandate_id})")
        # In production:
        # - Use SendGrid, AWS SES, or similar for email
        # - Use Twilio, AWS SNS, or similar for SMS


# Global instances
card_encryptor = CardEncryption()
webauthn_verifier = WebAuthnVerifier()
token_generator = PaymentTokenGenerator()
otp_manager = OTPManager()
