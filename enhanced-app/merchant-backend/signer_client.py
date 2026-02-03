"""
Signer Server Client
HTTP client for calling signer-server APIs
"""

import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SignerClient:
    """Client for Affinidi TDK Signer Server."""

    def __init__(self, signer_url: str = "http://localhost:8454"):
        """
        Initialize signer client.

        Args:
            signer_url: Base URL of signer server
        """
        self.signer_url = signer_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"SignerClient initialized for: {signer_url}")

    async def generate_did_web(self, domain: str) -> Dict[str, Any]:
        """
        Generate or retrieve DID:web wallet for domain.

        Args:
            domain: Domain name (e.g., "merchant.example.com")

        Returns:
            Wallet info including DID, did_document, wallet_id, signing_key_id
        """
        try:
            response = await self.client.post(
                f"{self.signer_url}/api/did-web-generate",
                json={"domain": domain}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to generate DID:web wallet: {e}")
            raise

    async def sign_jwt(
        self,
        domain: str,
        payload: Dict[str, Any],
        header: Dict[str, Any] = None
    ) -> str:
        """
        Sign a JWT with generic payload.

        Args:
            domain: Domain name
            payload: Complete JWT payload dict (with iss, sub, aud, iat, exp, etc.)
            header: Optional JWT header

        Returns:
            Signed JWT string
        """
        try:
            request_data = {
                "domain": domain,
                "payload": payload
            }
            if header:
                request_data["header"] = header

            response = await self.client.post(
                f"{self.signer_url}/api/sign-jwt",
                json=request_data
            )
            response.raise_for_status()
            result = response.json()
            return result["signed_jwt"]
        except httpx.HTTPError as e:
            logger.error(f"Failed to sign JWT: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error signing JWT: {e}", exc_info=True)
            raise

    async def sign_credential(
        self,
        domain: str,
        unsigned_credential: Dict[str, Any]
    ) -> str:
        """
        Sign a verifiable credential using the signer service.

        Args:
            domain: Domain name (e.g., "localhost:8453")
            unsigned_credential: Verifiable credential dict to sign

        Returns:
            Signed credential JWT string
        """
        try:
            response = await self.client.post(
                f"{self.signer_url}/api/sign-credential",
                json={
                    "domain": domain,
                    "unsigned_credential": unsigned_credential
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["signed_credential"]
        except httpx.HTTPError as e:
            logger.error(f"Failed to sign credential: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error signing credential: {e}", exc_info=True)
            raise

    async def verify_credential(self, jwt_vc: str) -> Dict[str, Any]:
        """
        Verify a verifiable credential using the signer service.

        Args:
            jwt_vc: JWT verifiable credential string to verify

        Returns:
            Verification result dict with fields:
            - valid: bool
            - verified: bool
            - error: Optional[str] (if invalid)
        """
        try:
            response = await self.client.post(
                f"{self.signer_url}/api/verify-credential",
                json={"jwt_vc": jwt_vc}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to verify credential: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error verifying credential: {e}", exc_info=True)
            raise

    async def cleanup(self):
        """Cleanup HTTP client."""
        await self.client.aclose()
