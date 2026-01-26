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

    def _generate_network_token_expiry(self, years_valid: int = 3) -> str:
        """
        Generate network token expiry in MM/YY format.
        UCP compliance: payment tokens should include network token expiry.

        Args:
            years_valid: Token validity in years (default: 3)

        Returns:
            Token expiry in MM/YY format (e.g., "12/28")
        """
        from datetime import timedelta
        expiry_date = datetime.utcnow() + timedelta(days=365 * years_valid)
        return expiry_date.strftime("%m/%y")

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

        # Generate payment token with network token expiry (UCP compliance)
        payment_token = self._generate_token_number()
        token_expiry = self._generate_network_token_expiry(years_valid=3)  # 3 years validity

        # Create payment mandate structure following AP2 protocol
        mandate = {
            "payment_mandate_contents": {
                "payment_mandate_id": mandate_id,
                "timestamp": datetime.utcnow().isoformat(),
                "payment_details_id": payment_request_id,
                "payment_details_total": {
                    "label": "Total",
                    "amount": {
                        "currency": "SGD",
                        "value": cart_data.get("total", 0.0)
                    }
                },
                "payment_response": {
                    "request_id": payment_request_id,
                    "method_name": "CARD",
                    "details": {
                        "token": payment_token,
                        "token_expiry": token_expiry,  # UCP compliance: network token expiry in MM/YY format
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

        logger.info(f"Created payment mandate: {mandate_id} with network token expiry: {token_expiry}")
        return mandate

    async def create_checkout_session(
        self,
        cart_items: list,
        buyer_email: str,
        promocode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create UCP checkout session.

        Args:
            cart_items: List of cart items
            buyer_email: Buyer's email
            promocode: Optional promocode/coupon code

        Returns:
            Checkout session data
        """
        try:
            payload = {
                "line_items": cart_items,
                "buyer_email": buyer_email,
                "currency": "SGD"
            }

            if promocode:
                payload["promocode"] = promocode

            response = await self.client.post(
                f"{self.merchant_url}/ucp/v1/checkout-sessions",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()
            session_data = response.json()

            logger.info(f"Created checkout session: {session_data.get('id')} with promocode: {promocode if promocode else 'none'}")
            return session_data

        except httpx.HTTPError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise

    async def update_checkout_with_mandate(
        self,
        session_id: str,
        mandate: Dict[str, Any],
        user_signature: str
    ) -> Dict[str, Any]:
        """
        Update UCP checkout session with AP2 payment mandate.

        Args:
            session_id: Checkout session ID
            mandate: Payment mandate
            user_signature: User signature

        Returns:
            Updated checkout session
        """
        try:
            response = await self.client.put(
                f"{self.merchant_url}/ucp/v1/checkout-sessions/{session_id}",
                json={
                    "payment_mandate": mandate,
                    "user_signature": user_signature
                },
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()
            session_data = response.json()

            logger.info(f"Updated checkout session {session_id} with payment mandate")
            return session_data

        except httpx.HTTPError as e:
            logger.error(f"Failed to update checkout session {session_id}: {e}")
            raise

    async def complete_checkout(
        self,
        session_id: str,
        otp_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete UCP checkout session.

        Args:
            session_id: Checkout session ID
            otp_code: Optional OTP code for verification

        Returns:
            Completion response with receipt
        """
        try:
            url = f"{self.merchant_url}/ucp/v1/checkout-sessions/{session_id}/complete"
            if otp_code:
                url = f"{url}?otp_code={otp_code}"

            response = await self.client.post(
                url,
                headers={"Content-Type": "application/json"}
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Completed checkout session {session_id}: {result.get('status')}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to complete checkout session {session_id}: {e}")
            raise

    def extract_otp_challenge(self, completion_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract OTP challenge from UCP checkout completion result.

        Args:
            completion_result: UCP checkout completion response

        Returns:
            OTP challenge info or None
        """
        # Check if status is otp_required
        if completion_result.get("status") == "otp_required":
            otp_challenge = completion_result.get("otp_challenge")
            if otp_challenge:
                logger.info(f"OTP challenge detected for checkout session")
                return otp_challenge

        return None
