"""Ollama-powered chat agent with UCP integration for shopping assistance."""

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from typing import List, Dict, Any, Optional
import logging

from ucp_client import UCPMerchantClient

logger = logging.getLogger(__name__)


class EnhancedBusinessAgent:
    """Enhanced business agent using Ollama LLM with UCP merchant integration."""

    def __init__(
        self,
        ollama_url: str = "http://host.docker.internal:11434",
        model_name: str = "qwen2.5:latest",
        merchant_url: str = "http://localhost:8451"
    ):
        self.llm = ChatOllama(
            base_url=ollama_url,
            model=model_name,
            temperature=0.7,
        )
        self.ucp_client = UCPMerchantClient(merchant_url)
        self.carts = {}  # In-memory cart storage: {session_id: [{product_id, name, price, quantity, sku}]}
        self.checkouts = {}  # In-memory checkout sessions
        self.orders = {}  # In-memory order history
        self.system_prompt = """You are a helpful shopping assistant for an online store.

You can help customers:
- Search for products in our catalog
- Answer questions about products
- Add items to their shopping cart
- View their shopping cart
- Help them find what they need

IMPORTANT INSTRUCTIONS:
1. When showing the cart, I will provide you with the ACTUAL cart contents - use that information.
2. When a user expresses intent to purchase/get/buy a product, I will automatically add it to their cart and show you a SUCCESS or FAILURE message.
3. If you see a "✅ SUCCESS" message in the conversation, acknowledge that the item was added to the cart.
4. If you see a "❌" message, inform the user that the product wasn't found.
5. When users ask to see their cart with phrases like "show my cart" or "what's in my cart", I will provide the complete cart contents.
6. IMPORTANT: When I provide product information with image URLs, you MUST include the images in your response using markdown image syntax: ![Product Name](image_url)
   - Place the image on its own line before the product name
   - Example format:
     ![Chocochip Cookies](https://images.unsplash.com/photo-xxx)
     **Chocochip Cookies** - $4.99
     Description here

Be friendly, helpful, and enthusiastic about helping customers shop!
When customers ask about products, I will provide you with the product information and image URLs from our catalog.
Always include product images when available.
Always be clear when items are successfully added to the cart.
"""

    async def initialize(self):
        """Initialize the agent by discovering UCP capabilities."""
        try:
            await self.ucp_client.discover_capabilities()
            logger.info("UCP client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize UCP client: {e}")

    async def search_products(self, query: str = None, limit: int = 10) -> List[Dict]:
        """
        Search for products via UCP client.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of products
        """
        try:
            products = await self.ucp_client.search_products(query=query, limit=limit)
            return products
        except Exception as e:
            logger.error(f"Failed to search products: {e}")
            return []

    def add_to_cart(self, session_id: str, product_id: str, name: str, price: float,
                    sku: str, quantity: int = 1, image_url: str = None) -> Dict[str, Any]:
        """
        Add a product to the user's cart.

        Args:
            session_id: User session identifier
            product_id: Product ID
            name: Product name
            price: Product price in dollars
            sku: Product SKU
            quantity: Quantity to add
            image_url: Product image URL (optional)

        Returns:
            Updated cart info
        """
        if session_id not in self.carts:
            self.carts[session_id] = []

        cart = self.carts[session_id]

        # Check if product already in cart
        existing_item = next((item for item in cart if item['product_id'] == product_id), None)

        if existing_item:
            existing_item['quantity'] += quantity
        else:
            cart_item = {
                'product_id': product_id,
                'sku': sku,
                'name': name,
                'price': price,
                'quantity': quantity
            }
            if image_url:
                cart_item['image_url'] = image_url
            cart.append(cart_item)

        total = sum(item['price'] * item['quantity'] for item in cart)

        return {
            'cart': cart,
            'total': total,
            'item_count': sum(item['quantity'] for item in cart)
        }

    def get_cart(self, session_id: str) -> Dict[str, Any]:
        """Get the current cart for a session."""
        cart = self.carts.get(session_id, [])
        total = sum(item['price'] * item['quantity'] for item in cart)

        return {
            'cart': cart,
            'total': total,
            'item_count': sum(item['quantity'] for item in cart)
        }

    def clear_cart(self, session_id: str):
        """Clear the cart for a session."""
        if session_id in self.carts:
            del self.carts[session_id]

    async def process_message(
        self,
        message: str,
        session_id: str = "default",
        chat_history: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Process a user message and return agent response.

        Args:
            message: User input message
            session_id: Session identifier
            chat_history: Previous conversation history

        Returns:
            Response dict with output and metadata
        """
        try:
            # Check if user is trying to add to cart
            msg_lower = message.lower()

            # Direct add keywords
            add_keywords = ['add', 'put', 'place', 'get', 'buy', 'purchase', 'order', 'want']
            has_add_keyword = any(keyword in msg_lower for keyword in add_keywords)

            # Product mentions
            product_keywords = ['cookie', 'chip', 'strawberr', 'bar', 'potato', 'oat', 'nutri']
            has_product_mention = any(keyword in msg_lower for keyword in product_keywords)

            # Cart/purchase context
            cart_context = ['cart', 'basket']
            has_cart_context = any(keyword in msg_lower for keyword in cart_context)

            # Check for affirmative responses that might be confirming an add-to-cart action
            is_affirmative = msg_lower.strip() in ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'yup']

            # Determine if this is an add-to-cart intent
            is_add_to_cart = (
                (has_add_keyword and (has_product_mention or has_cart_context)) or
                (is_affirmative and has_product_mention) or
                (has_add_keyword and has_product_mention)
            )

            # Check if user wants to checkout
            checkout_keywords = ['checkout', 'check out', 'pay', 'payment', 'complete order', 'finalize', 'proceed']
            is_checkout_intent = any(keyword in message.lower() for keyword in checkout_keywords)

            # Check if user is asking about cart
            cart_keywords = ['cart', 'basket', 'my order', 'what did i add', 'show me what']
            is_cart_query = any(keyword in message.lower() for keyword in cart_keywords) and not is_add_to_cart and not is_checkout_intent

            # Check if user is asking about products
            search_keywords = ['product', 'cookie', 'chip', 'strawberr', 'show', 'what', 'find', 'looking for', 'search']
            should_search = any(keyword in message.lower() for keyword in search_keywords) and not is_cart_query and not is_add_to_cart and not is_checkout_intent

            context = ""
            cart_action_result = None

            # Handle add to cart
            if is_add_to_cart:
                # Try to extract product name from message
                products = await self.search_products(limit=50)  # Get all products

                # Find matching product with improved matching logic
                matched_product = None
                msg_lower = message.lower()

                # Try exact match first
                for product in products:
                    product_name_lower = product['name'].lower()
                    if product_name_lower in msg_lower:
                        matched_product = product
                        break

                # If no exact match, try word-by-word matching
                if not matched_product:
                    max_matches = 0
                    for product in products:
                        product_words = set(product['name'].lower().split())
                        msg_words = set(msg_lower.split())
                        matches = len(product_words & msg_words)

                        # Require at least 1 matching word
                        if matches > max_matches:
                            max_matches = matches
                            matched_product = product

                    # Only use the match if we found at least one matching word
                    if max_matches == 0:
                        matched_product = None

                if matched_product:
                    # Add to cart
                    logger.info(f"Adding product to cart: {matched_product['name']} (ID: {matched_product['id']}) for session {session_id}")
                    cart_info = self.add_to_cart(
                        session_id=session_id,
                        product_id=matched_product['id'],
                        name=matched_product['name'],
                        price=matched_product['price'],
                        sku=matched_product.get('sku', matched_product['id']),
                        quantity=1,
                        image_url=matched_product.get('image_url')
                    )
                    logger.info(f"Cart updated: {cart_info['item_count']} items, Total: ${cart_info['total']:.2f}")
                    logger.info(f"Current cart contents: {[item['name'] for item in cart_info['cart']]}")

                    cart_action_result = f"\n\n✅ SUCCESS: I have added {matched_product['name']} (${matched_product['price']:.2f}) to your cart!\n"
                    cart_action_result += f"Cart now has {cart_info['item_count']} item(s), Total: ${cart_info['total']:.2f}\n"
                else:
                    logger.warning(f"Product not found for message: {message}")
                    cart_action_result = "\n\n❌ I couldn't find that product. Please specify the exact product name from our catalog.\n"

            # Add cart context if asking about cart OR checkout
            if is_cart_query or is_checkout_intent:
                cart_items = self.carts.get(session_id, [])
                if cart_items:
                    context += "\n\nCURRENT CART CONTENTS (show this to the user):\n"
                    total = 0
                    for item in cart_items:
                        item_total = item['price'] * item['quantity']
                        total += item_total
                        context += f"- {item['name']} x{item['quantity']} @ ${item['price']:.2f} each = ${item_total:.2f}\n"
                    context += f"\nCart Total: ${total:.2f}\n"

                    if is_checkout_intent:
                        context += "\nThe user wants to proceed to checkout. Confirm the cart contents and let them know the checkout popup will open.\n"
                else:
                    context += "\n\nThe user's cart is currently EMPTY.\n"
                    if is_checkout_intent:
                        context += "Tell them they need to add items before checkout.\n"

            # Add product search context
            if should_search:
                # Extract potential search query from the message
                search_query = None
                for keyword in ['cookie', 'chip', 'strawberr', 'bar', 'snack', 'fruit']:
                    if keyword in message.lower():
                        search_query = keyword
                        break

                products = await self.search_products(query=search_query)
                if products:
                    context += "\n\nAvailable products (include images in your response using markdown format):\n"
                    for p in products:
                        img_url = p.get('image_url', '')
                        context += f"- {p['name']} (${p['price']:.2f}) - {p.get('description', 'No description')}\n"
                        if img_url:
                            context += f"  Image: {img_url}\n"

            # Build conversation messages
            messages = [SystemMessage(content=self.system_prompt)]

            if chat_history:
                messages.extend(chat_history)

            user_message = message

            # Add cart action result if any
            if cart_action_result:
                user_message += cart_action_result

            # Add other context
            if context:
                user_message += context

            messages.append(HumanMessage(content=user_message))

            # Get response from LLM
            response = await self.llm.ainvoke(messages)

            # Include product data if this was a search query
            response_data = {
                "output": response.content,
                "session_id": session_id,
                "status": "success"
            }

            # If we searched for products, include them in the response
            if should_search and products:
                response_data["products"] = products

            return response_data

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "output": f"I apologize, but I encountered an error: {str(e)}. Please try again.",
                "session_id": session_id,
                "status": "error"
            }

    async def cleanup(self):
        """Cleanup resources."""
        await self.ucp_client.close()
