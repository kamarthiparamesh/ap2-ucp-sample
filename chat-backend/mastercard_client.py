"""
Mastercard API Client for Card on File Tokenization and Secure Authentication

This module integrates with Mastercard's sandbox APIs:
1. Card on File Tokenization - Tokenize payment cards for secure storage
2. Secure Card on File Authentication - Authenticate users during payment

Documentation:
- Card on File: https://developer.mastercard.com/mastercard-checkout-solutions/documentation/use-cases/card-on-file/
- Secure Card on File: https://developer.mastercard.com/mastercard-checkout-solutions/documentation/token-authentication/secure-card-on-file/by-mastercard/use-case1/
"""

import os
import json
import base64
import hashlib
import hmac
import time
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
import httpx
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class MastercardOAuth1Signer:
    """
    OAuth 1.0a signer for Mastercard API authentication.

    Mastercard APIs use OAuth 1.0a with RSA-SHA256 signature method.
    Reference: https://developer.mastercard.com/platform/documentation/security-and-authentication/
    """

    def __init__(self, consumer_key: str, signing_key_path: str):
        """
        Initialize OAuth signer.

        Args:
            consumer_key: Mastercard consumer key (API key)
            signing_key_path: Path to .p12 or .pem private key file
        """
        self.consumer_key = consumer_key
        self.signing_key = self._load_signing_key(signing_key_path)

    def _load_signing_key(self, key_path: str):
        """Load private key for signing requests."""
        if not os.path.exists(key_path):
            logger.warning(f"Signing key not found at {key_path}. OAuth signing disabled.")
            return None

        try:
            with open(key_path, 'rb') as key_file:
                key_data = key_file.read()

                # Try to load as PEM first
                try:
                    private_key = serialization.load_pem_private_key(
                        key_data,
                        password=None,
                        backend=default_backend()
                    )
                    return private_key
                except Exception:
                    # If PEM fails, try PKCS12 (.p12 file)
                    # Note: For .p12 files, you may need additional password handling
                    logger.error("Failed to load signing key. Please provide PEM format key.")
                    return None
        except Exception as e:
            logger.error(f"Error loading signing key: {e}")
            return None

    def sign_request(
        self,
        method: str,
        url: str,
        body: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate OAuth 1.0a signature for request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full request URL
            body: Request body (for POST/PUT requests)

        Returns:
            Authorization header dict
        """
        if not self.signing_key:
            logger.warning("Signing key not configured. Returning empty auth headers.")
            return {}

        # Generate OAuth parameters
        oauth_nonce = self._generate_nonce()
        oauth_timestamp = str(int(time.time()))

        oauth_params = {
            'oauth_consumer_key': self.consumer_key,
            'oauth_nonce': oauth_nonce,
            'oauth_signature_method': 'RSA-SHA256',
            'oauth_timestamp': oauth_timestamp,
            'oauth_version': '1.0'
        }

        # Generate signature base string
        signature_base = self._create_signature_base_string(
            method=method,
            url=url,
            oauth_params=oauth_params,
            body=body
        )

        # Sign with private key
        signature = self._sign_with_rsa(signature_base)
        oauth_params['oauth_signature'] = signature

        # Build Authorization header
        auth_header = 'OAuth ' + ', '.join(
            f'{key}="{value}"' for key, value in sorted(oauth_params.items())
        )

        return {'Authorization': auth_header}

    def _generate_nonce(self) -> str:
        """Generate random nonce for OAuth."""
        return base64.b64encode(uuid.uuid4().bytes).decode('utf-8').rstrip('=')

    def _create_signature_base_string(
        self,
        method: str,
        url: str,
        oauth_params: Dict[str, str],
        body: Optional[str] = None
    ) -> str:
        """Create OAuth signature base string."""
        # Parse URL to get base URL and query parameters
        from urllib.parse import urlparse, parse_qsl, urlencode, quote

        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"

        # Collect all parameters
        all_params = oauth_params.copy()

        # Add query parameters if present
        if parsed_url.query:
            query_params = dict(parse_qsl(parsed_url.query))
            all_params.update(query_params)

        # Add body hash if body is present
        if body:
            body_hash = base64.b64encode(
                hashlib.sha256(body.encode('utf-8')).digest()
            ).decode('utf-8')
            all_params['oauth_body_hash'] = body_hash

        # Sort parameters and create parameter string
        sorted_params = sorted(all_params.items())
        param_string = urlencode(sorted_params, quote_via=quote)

        # Create signature base string
        signature_base = '&'.join([
            method.upper(),
            quote(base_url, safe=''),
            quote(param_string, safe='')
        ])

        return signature_base

    def _sign_with_rsa(self, message: str) -> str:
        """Sign message with RSA-SHA256."""
        signature = self.signing_key.sign(
            message.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')


class MastercardTokenizationClient:
    """
    Client for Mastercard Card on File Tokenization API.

    This API allows merchants to tokenize payment cards for secure storage.
    Tokens can be used for recurring payments without storing actual card numbers.
    """

    def __init__(
        self,
        consumer_key: str,
        signing_key_path: str,
        sandbox: bool = True
    ):
        """
        Initialize Mastercard Tokenization client.

        Args:
            consumer_key: Mastercard API consumer key
            signing_key_path: Path to signing key (.p12 or .pem)
            sandbox: Use sandbox environment (default: True)
        """
        self.consumer_key = consumer_key
        self.sandbox = sandbox

        # Set API base URL
        if sandbox:
            self.base_url = "https://sandbox.api.mastercard.com"
        else:
            self.base_url = "https://api.mastercard.com"

        # Initialize OAuth signer
        self.signer = MastercardOAuth1Signer(consumer_key, signing_key_path)

        # HTTP client
        self.client = httpx.AsyncClient(timeout=30.0)

        logger.info(f"Mastercard Tokenization client initialized ({'sandbox' if sandbox else 'production'})")

    async def tokenize_card(
        self,
        card_number: str,
        expiry_month: int,
        expiry_year: int,
        security_code: Optional[str] = None,
        cardholder_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Tokenize a payment card.

        Args:
            card_number: Card number (PAN)
            expiry_month: Expiration month (1-12)
            expiry_year: Expiration year (YYYY)
            security_code: CVV/CVC (optional)
            cardholder_name: Name on card (optional)

        Returns:
            {
                "token": "4111111111111111",  # Network token
                "token_unique_reference": "DWSPMC000...",
                "pan_last_four": "1111",
                "card_network": "mastercard",
                "expiry_month": 12,
                "expiry_year": 2025,
                "token_assurance_level": "high"
            }
        """
        endpoint = "/mdes/digitization/1/0/tokenize"
        url = f"{self.base_url}{endpoint}"

        # Prepare request payload
        payload = {
            "requestId": str(uuid.uuid4()),
            "taskId": str(uuid.uuid4()),
            "tokenType": "CLOUD",
            "tokenRequestorId": self.consumer_key,
            "fundingAccountInfo": {
                "encryptedPayload": {
                    "accountNumber": card_number,
                    "expiryMonth": f"{expiry_month:02d}",
                    "expiryYear": str(expiry_year)
                }
            }
        }

        if cardholder_name:
            payload["cardholderInfo"] = {
                "accountHolderName": cardholder_name
            }

        if security_code:
            payload["fundingAccountInfo"]["encryptedPayload"]["securityCode"] = security_code

        body = json.dumps(payload)

        # Sign request
        headers = self.signer.sign_request('POST', url, body)
        headers['Content-Type'] = 'application/json'
        headers['Accept'] = 'application/json'

        try:
            response = await self.client.post(url, content=body, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Card tokenized successfully: {data.get('tokenUniqueReference', 'N/A')[:20]}...")

            # Transform response to standard format
            return {
                "token": data.get("token", {}).get("value"),
                "token_unique_reference": data.get("tokenUniqueReference"),
                "pan_last_four": card_number[-4:],
                "card_network": "mastercard",
                "expiry_month": expiry_month,
                "expiry_year": expiry_year,
                "token_assurance_level": data.get("tokenAssuranceLevel", "unknown"),
                "raw_response": data
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Tokenization API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Failed to tokenize card: {e.response.text}")
        except Exception as e:
            logger.error(f"Tokenization error: {e}")
            raise

    async def detokenize(self, token: str) -> Dict[str, Any]:
        """
        Detokenize a network token (retrieve original PAN).
        Note: This is typically restricted in production environments.

        Args:
            token: Network token to detokenize

        Returns:
            Original card details
        """
        endpoint = "/mdes/digitization/1/0/detokenize"
        url = f"{self.base_url}{endpoint}"

        payload = {
            "requestId": str(uuid.uuid4()),
            "tokenUniqueReference": token
        }

        body = json.dumps(payload)
        headers = self.signer.sign_request('POST', url, body)
        headers['Content-Type'] = 'application/json'

        try:
            response = await self.client.post(url, content=body, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Detokenization error: {e}")
            raise

    async def get_token_status(self, token_unique_reference: str) -> Dict[str, Any]:
        """
        Get status of a tokenized card.

        Args:
            token_unique_reference: Unique reference for the token

        Returns:
            Token status information
        """
        endpoint = f"/mdes/digitization/1/0/getToken"
        url = f"{self.base_url}{endpoint}"

        payload = {
            "requestId": str(uuid.uuid4()),
            "tokenUniqueReference": token_unique_reference
        }

        body = json.dumps(payload)
        headers = self.signer.sign_request('POST', url, body)
        headers['Content-Type'] = 'application/json'

        try:
            response = await self.client.post(url, content=body, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Get token status error: {e}")
            raise

    async def cleanup(self):
        """Close HTTP client."""
        await self.client.aclose()


class MastercardAuthenticationClient:
    """
    Client for Mastercard Secure Card on File Authentication API.

    This API provides additional authentication during payment transactions
    using tokenized cards.
    """

    def __init__(
        self,
        consumer_key: str,
        signing_key_path: str,
        sandbox: bool = True
    ):
        """
        Initialize Mastercard Authentication client.

        Args:
            consumer_key: Mastercard API consumer key
            signing_key_path: Path to signing key
            sandbox: Use sandbox environment
        """
        self.consumer_key = consumer_key
        self.sandbox = sandbox

        if sandbox:
            self.base_url = "https://sandbox.api.mastercard.com"
        else:
            self.base_url = "https://api.mastercard.com"

        self.signer = MastercardOAuth1Signer(consumer_key, signing_key_path)
        self.client = httpx.AsyncClient(timeout=30.0)

        logger.info(f"Mastercard Authentication client initialized ({'sandbox' if sandbox else 'production'})")

    async def initiate_authentication(
        self,
        token: str,
        amount: float,
        currency: str,
        merchant_id: str,
        transaction_id: str
    ) -> Dict[str, Any]:
        """
        Initiate authentication for a card-on-file transaction.

        Args:
            token: Network token
            amount: Transaction amount
            currency: Currency code (e.g., "SGD")
            merchant_id: Merchant identifier
            transaction_id: Unique transaction ID

        Returns:
            {
                "authentication_required": bool,
                "authentication_method": "otp" | "biometric" | "none",
                "challenge_id": str,
                "status": "pending" | "approved" | "declined"
            }
        """
        endpoint = "/scof/authentication/1/0/initiate"
        url = f"{self.base_url}{endpoint}"

        payload = {
            "requestId": str(uuid.uuid4()),
            "transactionId": transaction_id,
            "tokenUniqueReference": token,
            "amount": {
                "value": int(amount * 100),  # Convert to cents
                "currency": currency
            },
            "merchantId": merchant_id,
            "merchantName": "Enhanced Business Store",
            "authenticationChannel": "WEB"
        }

        body = json.dumps(payload)
        headers = self.signer.sign_request('POST', url, body)
        headers['Content-Type'] = 'application/json'

        try:
            response = await self.client.post(url, content=body, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Authentication initiated: {data.get('status', 'unknown')}")

            return {
                "authentication_required": data.get("authenticationRequired", False),
                "authentication_method": data.get("authenticationMethod", "none"),
                "challenge_id": data.get("challengeId"),
                "status": data.get("status", "pending"),
                "raw_response": data
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Authentication API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Failed to initiate authentication: {e.response.text}")
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise

    async def verify_authentication(
        self,
        challenge_id: str,
        verification_code: str
    ) -> Dict[str, Any]:
        """
        Verify authentication challenge (OTP or other method).

        Args:
            challenge_id: Challenge ID from initiate_authentication
            verification_code: User-provided verification code

        Returns:
            {
                "verified": bool,
                "status": "approved" | "declined",
                "message": str
            }
        """
        endpoint = "/scof/authentication/1/0/verify"
        url = f"{self.base_url}{endpoint}"

        payload = {
            "requestId": str(uuid.uuid4()),
            "challengeId": challenge_id,
            "verificationCode": verification_code
        }

        body = json.dumps(payload)
        headers = self.signer.sign_request('POST', url, body)
        headers['Content-Type'] = 'application/json'

        try:
            response = await self.client.post(url, content=body, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.info(f"Authentication verified: {data.get('status', 'unknown')}")

            return {
                "verified": data.get("status") == "approved",
                "status": data.get("status", "declined"),
                "message": data.get("message", ""),
                "raw_response": data
            }

        except Exception as e:
            logger.error(f"Verification error: {e}")
            raise

    async def cleanup(self):
        """Close HTTP client."""
        await self.client.aclose()


class MastercardClient:
    """
    Unified client for Mastercard Card on File and Authentication APIs.
    """

    def __init__(
        self,
        consumer_key: Optional[str] = None,
        signing_key_path: Optional[str] = None,
        sandbox: bool = True
    ):
        """
        Initialize Mastercard client with both tokenization and authentication.

        Args:
            consumer_key: Mastercard API consumer key (from env if not provided)
            signing_key_path: Path to signing key (from env if not provided)
            sandbox: Use sandbox environment (from env if not provided)
        """
        # Check if Mastercard integration is enabled
        mastercard_enabled = os.getenv("MASTERCARD_ENABLED", "false").lower() in ("true", "1", "yes")

        if not mastercard_enabled:
            logger.info("Mastercard API integration is disabled (MASTERCARD_ENABLED=false)")
            self.enabled = False
            self.tokenization = None
            self.authentication = None
            return

        # Get credentials from environment if not provided
        self.consumer_key = consumer_key or os.getenv("MASTERCARD_CONSUMER_KEY")
        self.signing_key_path = signing_key_path or os.getenv("MASTERCARD_SIGNING_KEY_PATH")

        # Get sandbox setting from environment
        if os.getenv("MASTERCARD_SANDBOX"):
            self.sandbox = os.getenv("MASTERCARD_SANDBOX", "true").lower() in ("true", "1", "yes")
        else:
            self.sandbox = sandbox

        # Check if credentials are configured
        self.enabled = bool(self.consumer_key and self.signing_key_path)

        if self.enabled:
            # Initialize sub-clients
            self.tokenization = MastercardTokenizationClient(
                self.consumer_key,
                self.signing_key_path,
                self.sandbox
            )
            self.authentication = MastercardAuthenticationClient(
                self.consumer_key,
                self.signing_key_path,
                self.sandbox
            )
            logger.info(f"Mastercard API client initialized successfully ({'sandbox' if self.sandbox else 'production'} mode)")
        else:
            logger.warning(
                "Mastercard API enabled but credentials not configured. "
                "Set MASTERCARD_CONSUMER_KEY and MASTERCARD_SIGNING_KEY_PATH environment variables."
            )
            self.tokenization = None
            self.authentication = None

    async def cleanup(self):
        """Close all HTTP clients."""
        if self.enabled:
            await self.tokenization.cleanup()
            await self.authentication.cleanup()


# Global Mastercard client instance (will be initialized in main.py)
mastercard_client: Optional[MastercardClient] = None
