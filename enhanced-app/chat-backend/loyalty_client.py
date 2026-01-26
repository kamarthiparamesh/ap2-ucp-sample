"""
Loyalty Client for Chat Backend (Consumer Agent)
Communicates with Merchant Backend's loyalty endpoints via UCP custom extension
"""

import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class LoyaltyClient:
    """
    Loyalty client for consumer agent (chat backend).
    Sends loyalty queries to merchant's loyalty agent via A2A.
    Implements UCP custom extension: com.enhancedbusiness.loyalty
    """

    def __init__(self, merchant_url: str):
        """
        Initialize loyalty client.

        Args:
            merchant_url: Base URL of merchant backend (e.g., http://localhost:8453)
        """
        self.merchant_url = merchant_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"Loyalty Client initialized for merchant: {merchant_url}")

    async def cleanup(self):
        """Cleanup HTTP client."""
        await self.client.aclose()

    async def query_loyalty(
        self,
        user_email: str,
        inquiry: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send loyalty inquiry to merchant agent (A2A communication).

        Args:
            user_email: User's email
            inquiry: Loyalty question/inquiry
            context: Optional context (cart, purchase info)

        Returns:
            Loyalty response from merchant agent
        """
        try:
            response = await self.client.post(
                f"{self.merchant_url}/api/loyalty/query",
                json={
                    "user_email": user_email,
                    "inquiry": inquiry,
                    "context": context
                },
                headers={
                    "Content-Type": "application/json",
                    "UCP-Agent": "chat-backend-consumer-agent",
                    "X-A2A-Extensions": "https://ucp.dev/specification/reference?v=2026-01-11"
                }
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Loyalty inquiry processed for {user_email}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to process loyalty inquiry: {e}")
            raise

    async def get_loyalty_status(self, user_email: str) -> Dict[str, Any]:
        """
        Get loyalty status for a user.

        Args:
            user_email: User's email

        Returns:
            Loyalty status
        """
        try:
            response = await self.client.post(
                f"{self.merchant_url}/api/loyalty/status",
                json={"user_email": user_email},
                headers={
                    "Content-Type": "application/json",
                    "UCP-Agent": "chat-backend-consumer-agent"
                }
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Loyalty status retrieved for {user_email}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to get loyalty status: {e}")
            raise

    async def redeem_loyalty_points(
        self,
        user_email: str,
        points: int,
        redemption_type: str = "discount"
    ) -> Dict[str, Any]:
        """
        Redeem loyalty points.

        Args:
            user_email: User's email
            points: Points to redeem
            redemption_type: Type of redemption

        Returns:
            Redemption result
        """
        try:
            response = await self.client.post(
                f"{self.merchant_url}/api/loyalty/redeem",
                json={
                    "user_email": user_email,
                    "points": points,
                    "redemption_type": redemption_type
                },
                headers={
                    "Content-Type": "application/json",
                    "UCP-Agent": "chat-backend-consumer-agent"
                }
            )

            response.raise_for_status()
            result = response.json()

            logger.info(f"Loyalty points redeemed for {user_email}: {points} points")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to redeem loyalty points: {e}")
            raise
