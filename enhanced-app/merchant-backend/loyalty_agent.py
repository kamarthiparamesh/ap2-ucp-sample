"""
Merchant Loyalty Agent - OLLAMA-based loyalty and rewards processor
Enables A2A communication for loyalty inquiries and rewards management
"""

import httpx
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class LoyaltyAgent:
    """
    Merchant-side loyalty agent for UCP loyalty A2A protocol.
    Uses OLLAMA to process loyalty inquiries and provide personalized rewards.
    """

    def __init__(self, ollama_url: str, model_name: str = "qwen2.5:8b"):
        """
        Initialize loyalty agent.

        Args:
            ollama_url: URL of OLLAMA server
            model_name: OLLAMA model to use for loyalty processing
        """
        self.ollama_url = ollama_url.rstrip('/')
        self.model_name = model_name
        self.client = httpx.AsyncClient(timeout=60.0)

        # In-memory loyalty data (in production, use database)
        self.user_loyalty_points: Dict[str, int] = {}  # email -> points
        self.loyalty_tiers: Dict[str, str] = {}  # email -> tier
        self.loyalty_history: Dict[str, List[Dict]] = {}  # email -> transactions

        logger.info(f"Loyalty Agent initialized (model: {model_name}, OLLAMA: {ollama_url})")

    async def cleanup(self):
        """Cleanup HTTP client."""
        await self.client.aclose()

    async def _query_ollama(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Query OLLAMA model for loyalty processing.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context

        Returns:
            Model response
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self.client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "stream": False
                }
            )

            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"OLLAMA query error: {e}")
            return f"Error processing loyalty inquiry: {str(e)}"

    def get_loyalty_status(self, user_email: str) -> Dict[str, Any]:
        """
        Get current loyalty status for a user.

        Args:
            user_email: User's email

        Returns:
            Loyalty status dict
        """
        points = self.user_loyalty_points.get(user_email, 0)
        tier = self.loyalty_tiers.get(user_email, "bronze")
        history = self.loyalty_history.get(user_email, [])

        return {
            "email": user_email,
            "points": points,
            "tier": tier,
            "tier_benefits": self._get_tier_benefits(tier),
            "transaction_count": len(history),
            "last_updated": datetime.utcnow().isoformat()
        }

    def _get_tier_benefits(self, tier: str) -> Dict[str, Any]:
        """Get benefits for loyalty tier."""
        benefits = {
            "bronze": {
                "discount_percentage": 5,
                "points_multiplier": 1.0,
                "perks": ["Basic rewards", "Birthday discount"]
            },
            "silver": {
                "discount_percentage": 10,
                "points_multiplier": 1.5,
                "perks": ["Enhanced rewards", "Free shipping", "Birthday discount", "Early access to sales"]
            },
            "gold": {
                "discount_percentage": 15,
                "points_multiplier": 2.0,
                "perks": ["Premium rewards", "Free express shipping", "Birthday discount",
                         "VIP access to sales", "Dedicated support"]
            },
            "platinum": {
                "discount_percentage": 20,
                "points_multiplier": 3.0,
                "perks": ["Exclusive rewards", "Free overnight shipping", "Birthday discount",
                         "First access to new products", "Concierge support", "Annual gift"]
            }
        }
        return benefits.get(tier, benefits["bronze"])

    async def process_loyalty_inquiry(
        self,
        user_email: str,
        inquiry: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process loyalty inquiry using OLLAMA (A2A communication).

        Args:
            user_email: User's email
            inquiry: Loyalty inquiry from consumer agent
            context: Additional context (cart, purchase history, etc.)

        Returns:
            Loyalty response
        """
        # Get user's current loyalty status
        loyalty_status = self.get_loyalty_status(user_email)

        # Prepare context for OLLAMA
        system_prompt = f"""You are a helpful loyalty rewards assistant for Enhanced Business Store.
You help customers understand their loyalty benefits and rewards.

Current loyalty program tiers:
- Bronze: 5% discount, 1x points
- Silver: 10% discount, 1.5x points, free shipping
- Gold: 15% discount, 2x points, free express shipping
- Platinum: 20% discount, 3x points, free overnight shipping

User's current status:
- Email: {user_email}
- Loyalty Points: {loyalty_status['points']}
- Current Tier: {loyalty_status['tier'].upper()}
- Tier Benefits: {json.dumps(loyalty_status['tier_benefits'], indent=2)}

Provide helpful, concise information about loyalty benefits, points, and tier progression.
Be friendly and encouraging about their loyalty journey."""

        # Add cart context if available
        if context and "cart" in context:
            cart_info = context["cart"]
            system_prompt += f"\n\nCurrent cart total: ${cart_info.get('total', 0):.2f}"

        # Query OLLAMA for response
        ollama_response = await self._query_ollama(
            prompt=inquiry,
            system_prompt=system_prompt
        )

        # Calculate potential points for cart (if provided)
        potential_points = 0
        if context and "cart" in context:
            cart_total = context["cart"].get("total", 0)
            multiplier = loyalty_status["tier_benefits"]["points_multiplier"]
            potential_points = int(cart_total * multiplier)

        return {
            "inquiry_id": f"LOY-{uuid.uuid4().hex[:12].upper()}",
            "user_email": user_email,
            "response": ollama_response,
            "loyalty_status": loyalty_status,
            "potential_points": potential_points,
            "timestamp": datetime.utcnow().isoformat()
        }

    def award_loyalty_points(
        self,
        user_email: str,
        points: int,
        transaction_id: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Award loyalty points to user.

        Args:
            user_email: User's email
            points: Points to award
            transaction_id: Associated transaction ID
            description: Description of points award

        Returns:
            Updated loyalty status
        """
        # Update points
        current_points = self.user_loyalty_points.get(user_email, 0)
        new_points = current_points + points
        self.user_loyalty_points[user_email] = new_points

        # Update tier based on points
        new_tier = self._calculate_tier(new_points)
        self.loyalty_tiers[user_email] = new_tier

        # Record transaction
        if user_email not in self.loyalty_history:
            self.loyalty_history[user_email] = []

        self.loyalty_history[user_email].append({
            "transaction_id": transaction_id,
            "points_earned": points,
            "description": description,
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info(f"Awarded {points} points to {user_email} (new total: {new_points}, tier: {new_tier})")

        return self.get_loyalty_status(user_email)

    def _calculate_tier(self, points: int) -> str:
        """Calculate loyalty tier based on points."""
        if points >= 10000:
            return "platinum"
        elif points >= 5000:
            return "gold"
        elif points >= 2000:
            return "silver"
        else:
            return "bronze"

    def redeem_loyalty_points(
        self,
        user_email: str,
        points_to_redeem: int,
        redemption_type: str = "discount"
    ) -> Dict[str, Any]:
        """
        Redeem loyalty points.

        Args:
            user_email: User's email
            points_to_redeem: Points to redeem
            redemption_type: Type of redemption (discount, gift, etc.)

        Returns:
            Redemption result
        """
        current_points = self.user_loyalty_points.get(user_email, 0)

        if points_to_redeem > current_points:
            return {
                "success": False,
                "error": f"Insufficient points. You have {current_points} points, need {points_to_redeem}."
            }

        # Deduct points
        new_points = current_points - points_to_redeem
        self.user_loyalty_points[user_email] = new_points

        # Calculate redemption value (1 point = $0.01)
        redemption_value = points_to_redeem * 0.01

        # Record redemption
        if user_email not in self.loyalty_history:
            self.loyalty_history[user_email] = []

        redemption_id = f"RED-{uuid.uuid4().hex[:8].upper()}"
        self.loyalty_history[user_email].append({
            "redemption_id": redemption_id,
            "points_redeemed": -points_to_redeem,
            "redemption_value": redemption_value,
            "redemption_type": redemption_type,
            "description": f"Redeemed {points_to_redeem} points for ${redemption_value:.2f} {redemption_type}",
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info(f"User {user_email} redeemed {points_to_redeem} points for ${redemption_value:.2f}")

        return {
            "success": True,
            "redemption_id": redemption_id,
            "points_redeemed": points_to_redeem,
            "redemption_value": redemption_value,
            "new_points_balance": new_points,
            "loyalty_status": self.get_loyalty_status(user_email)
        }
