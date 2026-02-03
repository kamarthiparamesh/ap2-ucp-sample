"""
Merchant Payment Agent - Ollama-based AP2 payment processor
Integrated within merchant backend, uses same Ollama instance as chat backend.
"""

import uuid
import random
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from ap2_types import (
    PaymentMandate,
    PaymentReceipt,
    PaymentReceiptSuccess,
    PaymentReceiptError,
    PaymentReceiptFailure,
    PaymentCurrencyAmount,
    OTPChallenge
)

logger = logging.getLogger(__name__)


class MerchantPaymentAgent:
    """
    Merchant-side payment agent for AP2 protocol.
    Receives signed payment mandates from consumer and processes payments.
    """

    def __init__(self, ollama_url: Optional[str] = None, model_name: str = "qwen2.5:8b", signer_client=None):
        """
        Initialize merchant payment agent.

        Args:
            ollama_url: URL of Ollama server (optional, can use same as chat backend)
            model_name: Ollama model to use for payment processing logic
            signer_client: SignerClient instance for credential verification
        """
        self.ollama_url = ollama_url
        self.signer_client = signer_client
        self.model_name = model_name
        self.pending_otps: Dict[str, str] = {}  # mandate_id -> otp

        # OTP configuration - can be enabled/disabled via environment variable
        # Set ENABLE_OTP_CHALLENGE=true to enable OTP for high-risk transactions
        # Default: false (disabled) since passkeys provide sufficient security
        self.otp_enabled = os.getenv(
            "ENABLE_OTP_CHALLENGE", "false").lower() == "true"
        self.otp_amount_threshold = float(
            os.getenv("OTP_AMOUNT_THRESHOLD", "100.0"))

        logger.info(
            f"Merchant Payment Agent initialized (model: {model_name}, OTP: {'enabled' if self.otp_enabled else 'disabled'})")

    def validate_token_expiry(self, mandate: PaymentMandate) -> bool:
        """
        Validate payment token expiry (UCP compliance).
        Checks if the network token has not expired.
        Expects token_expiry in MM/YY format (e.g., "12/28").

        Args:
            mandate: Payment mandate with token details

        Returns:
            True if token is valid (not expired), False otherwise
        """
        # Extract token expiry from payment response details
        token_expiry_str = mandate.payment_mandate_contents.payment_response.details.get(
            "token_expiry")

        if not token_expiry_str:
            logger.warning(
                f"Mandate {mandate.payment_mandate_contents.payment_mandate_id} missing token_expiry")
            # For backward compatibility, accept mandates without expiry
            return True

        try:
            # Parse expiry in MM/YY format
            month_str, year_str = token_expiry_str.split("/")
            month = int(month_str)
            year = 2000 + int(year_str)  # Convert YY to YYYY

            # Create expiry date (last day of the expiry month)
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            expiry_date = datetime(year, month, last_day, 23, 59, 59)

            # Check if token has expired
            now = datetime.utcnow()
            if now > expiry_date:
                logger.warning(
                    f"Mandate {mandate.payment_mandate_contents.payment_mandate_id} network token expired at {token_expiry_str}")
                return False

            logger.info(
                f"Mandate {mandate.payment_mandate_contents.payment_mandate_id} network token valid until {token_expiry_str}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to parse network token expiry for mandate {mandate.payment_mandate_contents.payment_mandate_id}: {e}")
            # For backward compatibility, accept if parsing fails
            return True

    def validate_mandate_signature(self, mandate: PaymentMandate) -> bool:
        """
        Validate payment mandate signature.
        In production, this would verify the WebAuthn signature.
        For demo, we check if signature exists.
        """
        if not mandate.user_authorization:
            logger.warning(
                f"Mandate {mandate.payment_mandate_contents.payment_mandate_id} missing signature")
            return False

        # In production: verify signature using public key from consumer
        # For demo: accept if signature exists and is non-empty
        if len(mandate.user_authorization) < 10:
            logger.warning(
                f"Mandate {mandate.payment_mandate_contents.payment_mandate_id} has invalid signature")
            return False

        logger.info(
            f"Mandate {mandate.payment_mandate_contents.payment_mandate_id} signature validated")
        return True

    async def validate_merchant_authorization(self, mandate: PaymentMandate) -> bool:
        """
        Validate merchant authorization credential.
        This verifies the merchant's verifiable credential signature.
        """
        if not mandate.merchant_authorization:
            logger.warning(
                f"Mandate {mandate.payment_mandate_contents.payment_mandate_id} missing merchant authorization")
            return False

        if not self.signer_client:
            logger.error(
                "Signer client not initialized - cannot verify merchant authorization")
            return False

        try:
            logger.info(
                f"Verifying merchant authorization for mandate {mandate.payment_mandate_contents.payment_mandate_id}")
            verification_result = await self.signer_client.verify_credential(
                jwt_vc=mandate.merchant_authorization
            )

            if not verification_result.get("valid") or not verification_result.get("verified"):
                error_msg = verification_result.get(
                    "error", "Unknown verification error")
                logger.error(
                    f"Merchant authorization verification failed: {error_msg}")
                return False

            logger.info(
                f"Merchant authorization verified successfully for mandate {mandate.payment_mandate_contents.payment_mandate_id}")

            return verification_result.get("valid")

        except Exception as e:
            logger.error(
                f"Error verifying merchant authorization: {e}", exc_info=True)
            return False

    def should_raise_otp_challenge(self, mandate: PaymentMandate) -> bool:
        """
        Determine if OTP challenge should be raised.

        Configurable via environment variables:
        - ENABLE_OTP_CHALLENGE=true/false (default: false)
        - OTP_AMOUNT_THRESHOLD=<amount> (default: 100.0)

        NOTE: OTP is disabled by default since we use passkeys (WebAuthn/FIDO2)
        for authentication and payment signing. Passkeys already provide:
        - Phishing-resistant authentication
        - Multi-factor authentication (possession + biometric/PIN)
        - Cryptographic signature per transaction

        Enable OTP only if you need additional step-up authentication for:
        - Regulatory compliance requirements
        - High-value transactions (configurable threshold)
        - Extra risk management layer
        """
        # Check if OTP is enabled
        if not self.otp_enabled:
            logger.info(
                f"OTP disabled for mandate {mandate.payment_mandate_contents.payment_mandate_id}")
            return False

        # OTP enabled - check amount threshold
        amount = mandate.payment_mandate_contents.payment_details_total.amount.value

        if amount > self.otp_amount_threshold:
            logger.info(
                f"OTP challenge triggered for mandate {mandate.payment_mandate_contents.payment_mandate_id} (amount: ${amount} > threshold: ${self.otp_amount_threshold})")
            return True

        logger.info(
            f"No OTP challenge for mandate {mandate.payment_mandate_contents.payment_mandate_id} (amount: ${amount} <= threshold: ${self.otp_amount_threshold})")
        return False

    def generate_otp(self, mandate_id: str) -> str:
        """
        Generate OTP for payment verification.
        For demo purposes, always returns 123456.
        In production, this would generate a random OTP and send via SMS/email.
        """
        otp = '123456'  # Fixed OTP for demo purposes
        self.pending_otps[mandate_id] = otp
        logger.info(
            f"Generated OTP for mandate {mandate_id}: {otp} (demo mode)")
        return otp

    def verify_otp(self, mandate_id: str, otp_code: str) -> bool:
        """Verify OTP code."""
        expected_otp = self.pending_otps.get(mandate_id)

        if not expected_otp:
            logger.warning(f"No OTP found for mandate {mandate_id}")
            return False

        if otp_code == expected_otp:
            # Remove OTP after successful verification
            del self.pending_otps[mandate_id]
            logger.info(f"OTP verified successfully for mandate {mandate_id}")
            return True

        logger.warning(f"Invalid OTP for mandate {mandate_id}")
        return False

    async def process_payment(self, mandate: PaymentMandate) -> PaymentReceipt:
        """
        Process payment mandate and return receipt.

        This is the main AP2 payment processing flow:
        1. Validate mandate signature
        2. Validate merchant authorization credential
        3. Validate token expiry (UCP compliance)
        4. Process payment (simulate)
        5. Return receipt
        """
        mandate_id = mandate.payment_mandate_contents.payment_mandate_id

        # Validate signature
        if not self.validate_mandate_signature(mandate):
            return PaymentReceipt(
                payment_mandate_id=mandate_id,
                timestamp=datetime.utcnow().isoformat(),
                payment_id=f"ERR-{uuid.uuid4().hex[:8]}",
                amount=mandate.payment_mandate_contents.payment_details_total.amount,
                payment_status=PaymentReceiptError(
                    error_message="Invalid mandate signature"
                )
            )

        # Validate merchant authorization credential
        if mandate.merchant_authorization:
            try:
                is_valid = await self.validate_merchant_authorization(mandate)
                if not is_valid:
                    return PaymentReceipt(
                        payment_mandate_id=mandate_id,
                        timestamp=datetime.utcnow().isoformat(),
                        payment_id=f"ERR-{uuid.uuid4().hex[:8]}",
                        amount=mandate.payment_mandate_contents.payment_details_total.amount,
                        payment_status=PaymentReceiptError(
                            error_message="Invalid merchant authorization credential"
                        )
                    )
            except Exception as e:
                logger.error(
                    f"Error in merchant authorization validation: {e}")
                return PaymentReceipt(
                    payment_mandate_id=mandate_id,
                    timestamp=datetime.utcnow().isoformat(),
                    payment_id=f"ERR-{uuid.uuid4().hex[:8]}",
                    amount=mandate.payment_mandate_contents.payment_details_total.amount,
                    payment_status=PaymentReceiptError(
                        error_message=f"Merchant authorization verification error: {str(e)}"
                    )
                )

        # Validate token expiry (UCP compliance)
        if not self.validate_token_expiry(mandate):
            return PaymentReceipt(
                payment_mandate_id=mandate_id,
                timestamp=datetime.utcnow().isoformat(),
                payment_id=f"ERR-{uuid.uuid4().hex[:8]}",
                amount=mandate.payment_mandate_contents.payment_details_total.amount,
                payment_status=PaymentReceiptError(
                    error_message="Payment token expired. Please retry the transaction."
                )
            )

        # Simulate payment processing
        # In production: call actual payment gateway
        payment_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
        merchant_confirmation = f"MCH-{uuid.uuid4().hex[:8].upper()}"
        psp_confirmation = f"PSP-{uuid.uuid4().hex[:8].upper()}"
        network_confirmation = f"NET-{uuid.uuid4().hex[:8].upper()}"

        logger.info(
            f"Processing payment for mandate {mandate_id}: {payment_id}")

        # Simulate success (95% success rate)
        if random.random() < 0.95:
            receipt = PaymentReceipt(
                payment_mandate_id=mandate_id,
                timestamp=datetime.utcnow().isoformat(),
                payment_id=payment_id,
                amount=mandate.payment_mandate_contents.payment_details_total.amount,
                payment_status=PaymentReceiptSuccess(
                    merchant_confirmation_id=merchant_confirmation,
                    psp_confirmation_id=psp_confirmation,
                    network_confirmation_id=network_confirmation
                ),
                payment_method_details={
                    "method": mandate.payment_mandate_contents.payment_response.method_name,
                    "payer_email": mandate.payment_mandate_contents.payment_response.payer_email
                }
            )
            logger.info(f"Payment successful: {payment_id}")
        else:
            # Simulate failure
            receipt = PaymentReceipt(
                payment_mandate_id=mandate_id,
                timestamp=datetime.utcnow().isoformat(),
                payment_id=payment_id,
                amount=mandate.payment_mandate_contents.payment_details_total.amount,
                payment_status=PaymentReceiptFailure(
                    failure_message="Payment declined by issuing bank"
                )
            )
            logger.warning(f"Payment failed: {payment_id}")

        return receipt

    def create_otp_challenge(self, mandate: PaymentMandate) -> OTPChallenge:
        """Create OTP challenge for mandate."""
        mandate_id = mandate.payment_mandate_contents.payment_mandate_id
        otp = self.generate_otp(mandate_id)

        # In production: send OTP via SMS/email
        # For demo: just log it
        payer_email = mandate.payment_mandate_contents.payment_response.payer_email

        return OTPChallenge(
            payment_mandate_id=mandate_id,
            message=f"OTP verification required. Code sent to {payer_email}",
            otp_sent_to=payer_email
        )
