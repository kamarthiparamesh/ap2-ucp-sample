"""
Chat Backend - AI Shopping Assistant
Uses UCP client to communicate with Merchant Backend
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uvicorn
import os
from datetime import datetime
from dotenv import load_dotenv
import logging

from ollama_agent import EnhancedBusinessAgent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class ChatMessage(BaseModel):
    """Chat message from user."""
    message: str
    session_id: str = "default"
    checkout_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat agent."""
    response: str
    session_id: str
    status: str


class CartItem(BaseModel):
    """Cart item model."""
    product_id: str
    sku: str
    name: str
    price: float
    quantity: int


class CheckoutRequest(BaseModel):
    """Checkout request model."""
    items: List[CartItem]
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None


class CheckoutResponse(BaseModel):
    """Checkout response model."""
    checkout_id: str
    items: List[CartItem]
    total: float
    currency: str
    status: str
    created_at: str


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    # Startup
    ollama_url = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")
    merchant_url = os.getenv("MERCHANT_BACKEND_URL", "http://localhost:8451")

    app.state.agent = EnhancedBusinessAgent(
        ollama_url=ollama_url,
        model_name=ollama_model,
        merchant_url=merchant_url
    )

    # Initialize UCP client
    await app.state.agent.initialize()
    logger.info(f"Chat backend initialized with merchant at {merchant_url}")

    yield

    # Shutdown
    await app.state.agent.cleanup()
    logger.info("Chat backend shutdown complete")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Chat Backend API",
    description="AI-powered shopping assistant with UCP integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_agent() -> EnhancedBusinessAgent:
    """Get agent instance."""
    return app.state.agent


# ============================================================================
# Chat Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - provides API information."""
    return {
        "service": "Chat Backend API",
        "version": "1.0.0",
        "description": "AI-powered shopping assistant with UCP integration",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "api": {
                "chat": "POST /api/chat",
                "checkout": "POST /api/checkout",
                "get_checkout": "GET /api/checkout/{checkout_id}",
                "get_order": "GET /api/orders/{order_id}"
            }
        },
        "frontend_url": "http://localhost:3000",
        "status": "running"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    agent: EnhancedBusinessAgent = Depends(get_agent)
):
    """
    Send a message to the shopping assistant agent.
    The agent will use UCP to query products from the merchant backend.
    """
    result = await agent.process_message(
        message=message.message,
        session_id=message.session_id
    )

    return ChatResponse(
        response=result["output"],
        session_id=result["session_id"],
        status=result["status"]
    )


@app.post("/api/checkout", response_model=CheckoutResponse, status_code=201)
async def create_checkout(
    checkout_request: CheckoutRequest,
    agent: EnhancedBusinessAgent = Depends(get_agent)
):
    """Create a new checkout session and process purchase."""
    import uuid

    # Generate unique checkout ID
    checkout_id = str(uuid.uuid4())

    # Calculate total
    total = sum(item.price * item.quantity for item in checkout_request.items)

    # Create checkout session
    checkout_data = {
        "checkout_id": checkout_id,
        "items": [item.dict() for item in checkout_request.items],
        "total": total,
        "currency": "USD",
        "status": "completed",
        "customer_name": checkout_request.customer_name,
        "customer_email": checkout_request.customer_email,
        "customer_phone": checkout_request.customer_phone,
        "created_at": datetime.now().isoformat()
    }

    # Store checkout in memory
    agent.checkouts[checkout_id] = checkout_data

    # Also store as an order for history
    agent.orders[checkout_id] = checkout_data

    return CheckoutResponse(
        checkout_id=checkout_id,
        items=checkout_request.items,
        total=total,
        currency="USD",
        status="completed",
        created_at=checkout_data["created_at"]
    )


@app.get("/api/checkout/{checkout_id}")
async def get_checkout(
    checkout_id: str,
    agent: EnhancedBusinessAgent = Depends(get_agent)
):
    """Get current checkout details."""
    if checkout_id in agent.checkouts:
        return {"checkout": agent.checkouts[checkout_id]}
    raise HTTPException(status_code=404, detail="Checkout not found")


@app.get("/api/orders/{order_id}")
async def get_order(
    order_id: str,
    agent: EnhancedBusinessAgent = Depends(get_agent)
):
    """Get order details."""
    if order_id in agent.orders:
        return {"order": agent.orders[order_id]}
    raise HTTPException(status_code=404, detail="Order not found")


# ============================================================================
# Cart Endpoints
# ============================================================================

@app.get("/api/cart/{session_id}")
async def get_cart(
    session_id: str,
    agent: EnhancedBusinessAgent = Depends(get_agent)
):
    """Get cart for a session."""
    cart_info = agent.get_cart(session_id)
    return cart_info


@app.post("/api/cart/{session_id}/add")
async def add_to_cart(
    session_id: str,
    item: CartItem,
    agent: EnhancedBusinessAgent = Depends(get_agent)
):
    """Add item to cart."""
    cart_info = agent.add_to_cart(
        session_id=session_id,
        product_id=item.product_id,
        name=item.name,
        price=item.price,
        sku=item.sku,
        quantity=item.quantity
    )
    return cart_info


@app.delete("/api/cart/{session_id}")
async def clear_cart(
    session_id: str,
    agent: EnhancedBusinessAgent = Depends(get_agent)
):
    """Clear cart for a session."""
    agent.clear_cart(session_id)
    return {"message": "Cart cleared successfully"}


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "chat-backend",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8450))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
