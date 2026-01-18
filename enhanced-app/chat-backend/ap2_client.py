"""
AP2 Client for Chat Backend (Consumer Agent)
Communicates with Merchant Backend's AP2 payment endpoints
"""

import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import random

logger = logging.getLogger(__name__)


class AP2Client:
    """
    AP2 client for consumer agent (chat backend).
    Sends payment mandates to merchant's AP2 payment processor.
    """

    def __init__(self, merchant_url: str):
        """
        Initialize AP2 client.

        Args:
            merchant_url: Base URL of merchant backend (e.g., http://localhost:8453)
        """
        self.merchant_url = merchant_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"AP2 Client initialized for merchant: {merchant_url}")

    async def cleanup(self):
        """Cleanup HTTP client."""
        await self.client.aclose()

    def _generate_token_number(self) -> str:
        """
        Generate a 16-digit token number for payment.
        Similar format to: 5342223122345000
        """
        # Generate 16 random digits
        return ''.join([str(random.randint(0, 9)) for _ in range(16)])

    def _generate_cryptogram(self) -> str:
        """
        Generate a random cryptogram for payment security.
        Returns a 32-character hexadecimal string.
        """
        return uuid.uuid4().hex.upper()

    def create_payment_mandate(
        self,
        cart_data: Dict[str, Any],
        payment_card: Dict[str, Any],
        user_email: str,
        user_signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create AP2 payment mandate from cart and card data.

        Args:
            cart_data: Cart information (items, total, etc.)
            payment_card: Payment card info (masked)
            user_email: User's email
            user_signature: WebAuthn signature (if already signed)

        Returns:
            Payment mandate dict
        """
        mandate_id = f"PM-{uuid.uuid4().hex[:16].upper()}"
        payment_request_id = f"REQ-{uuid.uuid4().hex[:12].upper()}"

        # Create payment mandate structure following AP2 protocol
        mandate = {
            "payment_mandate_contents": {
                "payment_mandate_id": mandate_id,
                "timestamp": datetime.utcnow().isoformat(),
                "payment_details_id": payment_request_id,
                "payment_details_total": {
                    "label": "Total",
                    "amount": {
                        "currency": "USD",
                        "value": cart_data.get("total", 0.0)
                    }
                },
                "payment_response": {
                    "request_id": payment_request_id,
                    "method_name": "CARD",
                    "details": {
                        "token": self._generate_token_number(),
                        "cryptogram": self._generate_cryptogram(),
                        "card_last_four": payment_card.get("card_last_four"),
                        "card_network": payment_card.get("card_network")
                    },
                    "payer_email": user_email,
                    "payer_name": payment_card.get("card_holder_name")
                },
                "merchant_agent": "merchant-001"
            },
            "user_authorization": user_signature  # Will be added when user signs
        }

        logger.info(f"Created payment mandate: {mandate_id}")
        return mandate

    async def send_payment_mandate(self, mandate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send signed payment mandate to merchant's AP2 payment processor.

        Args:
            mandate: Signed payment mandate

        Returns:
            Payment receipt from merchant
        """
        mandate_id = mandate["payment_mandate_contents"]["payment_mandate_id"]

        try:
            response = await self.client.post(
                f"{self.merchant_url}/ap2/payment/process",
                json=mandate,
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()
            receipt = response.json()

            logger.info(f"Payment processed for mandate {mandate_id}: {receipt.get('payment_status')}")
            return receipt

        except httpx.HTTPError as e:
            logger.error(f"Failed to process payment mandate {mandate_id}: {e}")
            raise

    async def verify_otp_and_process(
        self,
        mandate: Dict[str, Any],
        otp_code: str
    ) -> Dict[str, Any]:
        """
        Verify OTP and process payment.

        Args:
            mandate: Payment mandate
            otp_code: OTP code from user

        Returns:
            Payment receipt
        """
        mandate_id = mandate["payment_mandate_contents"]["payment_mandate_id"]

        try:
            response = await self.client.post(
                f"{self.merchant_url}/ap2/payment/verify-otp",
                json={
                    "mandate": mandate,
                    "otp_verification": {
                        "payment_mandate_id": mandate_id,
                        "otp_code": otp_code
                    }
                },
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()
            receipt = response.json()

            logger.info(f"OTP verified and payment processed for mandate {mandate_id}")
            return receipt

        except httpx.HTTPError as e:
            logger.error(f"Failed to verify OTP for mandate {mandate_id}: {e}")
            raise

    def extract_otp_challenge(self, receipt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract OTP challenge from receipt if present.

        Args:
            receipt: Payment receipt

        Returns:
            OTP challenge info or None
        """
        payment_status = receipt.get("payment_status", {})

        # Check if it's an error status with OTP required
        if "error_message" in payment_status:
            error_msg = payment_status["error_message"]
            if error_msg.startswith("OTP_REQUIRED:"):
                # Extract OTP challenge from payment_method_details
                otp_challenge = receipt.get("payment_method_details", {}).get("otp_challenge")
                if otp_challenge:
                    logger.info(f"OTP challenge detected for mandate {receipt.get('payment_mandate_id')}")
                    return otp_challenge

        return None
