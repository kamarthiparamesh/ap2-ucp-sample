"""
UCP Client for communicating with Merchant Backend
"""

import httpx
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class UCPMerchantClient:
    """Client for interacting with UCP-compliant merchant backend."""

    def __init__(self, merchant_url: str):
        """
        Initialize UCP client.

        Args:
            merchant_url: Base URL of the merchant backend
        """
        self.merchant_url = merchant_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.ucp_profile = None

    async def discover_capabilities(self) -> Dict[str, Any]:
        """
        Discover merchant capabilities via UCP discovery endpoint.

        Returns:
            UCP profile with capabilities and endpoints
        """
        try:
            response = await self.client.get(f"{self.merchant_url}/.well-known/ucp")
            response.raise_for_status()
            self.ucp_profile = response.json()
            logger.info(f"Discovered UCP profile: {self.ucp_profile}")
            return self.ucp_profile
        except Exception as e:
            logger.error(f"Failed to discover UCP capabilities: {e}")
            raise

    async def search_products(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search products using UCP product search endpoint.

        Args:
            query: Search query string
            category: Product category filter
            limit: Maximum number of results

        Returns:
            List of product items
        """
        try:
            params = {"limit": limit}
            if query:
                params["q"] = query
            if category:
                params["category"] = category

            response = await self.client.get(
                f"{self.merchant_url}/ucp/products/search",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            # Convert UCP format (cents) back to dollars
            products = []
            for item in data.get("items", []):
                # Parse image_url from JSON array string
                image_url = item.get("image_url")
                if image_url and isinstance(image_url, str):
                    try:
                        import json
                        urls = json.loads(image_url)
                        image_url = urls[0] if urls else None
                    except (json.JSONDecodeError, IndexError):
                        image_url = None

                products.append({
                    "id": item["id"],
                    "name": item["title"],
                    "description": item.get("description"),
                    "price": item["price"] / 100.0,  # Convert cents to dollars
                    "currency": "USD",
                    "image_url": image_url
                })

            return products

        except Exception as e:
            logger.error(f"Failed to search products: {e}")
            return []

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
