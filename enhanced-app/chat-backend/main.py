"""
Chat Backend - AI Shopping Assistant
Uses UCP client to communicate with Merchant Backend
Acts as Credentials Provider for AP2 payment protocol
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
import uuid
import json

from ollama_agent import EnhancedBusinessAgent
from database import db_manager, User, PaymentCard, PaymentMandate, PaymentReceipt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from payment_utils import (
    card_encryptor,
    webauthn_verifier,
    token_generator,
    otp_manager
)
from ap2_client import AP2Client

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
# Payment & Authentication Models
# ============================================================================

class UserRegistration(BaseModel):
    """Model for user registration with passkey."""
    email: str
    display_name: str
    client_data_json: str  # WebAuthn client data
    attestation_object: str  # WebAuthn attestation
    challenge: str


class UserRegistrationResponse(BaseModel):
    """Response for user registration."""
    user_id: str
    email: str
    display_name: str
    credential_id: str
    default_card: Dict[str, Any]


class ChallengeRequest(BaseModel):
    """Request for WebAuthn challenge."""
    email: str


class ChallengeResponse(BaseModel):
    """Response with WebAuthn challenge."""
    challenge: str
    timeout: int = 60000  # 60 seconds


class PasskeyVerification(BaseModel):
    """Model for passkey verification."""
    email: str
    credential_id: str
    client_data_json: str
    authenticator_data: str
    signature: str
    challenge: str


class PaymentCardResponse(BaseModel):
    """Response model for payment card (masked)."""
    id: str
    user_email: str
    card_last_four: str
    card_network: str
    card_holder_name: Optional[str]
    is_default: bool
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

    # Initialize database for user credentials
    db_manager.init_db()
    logger.info("Chat backend database initialized")

    app.state.agent = EnhancedBusinessAgent(
        ollama_url=ollama_url,
        model_name=ollama_model,
        merchant_url=merchant_url
    )

    # Initialize UCP client
    await app.state.agent.initialize()
    logger.info(f"Chat backend initialized with merchant at {merchant_url}")

    # Initialize AP2 client
    app.state.ap2_client = AP2Client(merchant_url)
    logger.info("AP2 client initialized")

    yield

    # Shutdown
    await app.state.agent.cleanup()
    await app.state.ap2_client.cleanup()
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


async def get_db() -> AsyncSession:
    """Get database session."""
    async for session in db_manager.get_session():
        yield session


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
# Authentication & User Endpoints (Credentials Provider)
# ============================================================================

@app.post("/api/auth/challenge", response_model=ChallengeResponse)
async def get_registration_challenge(request: ChallengeRequest):
    """Generate WebAuthn challenge for registration or authentication."""
    challenge = webauthn_verifier.generate_challenge()
    return ChallengeResponse(challenge=challenge)


@app.post("/api/auth/register", response_model=UserRegistrationResponse, status_code=201)
async def register_user(
    registration: UserRegistration,
    session: AsyncSession = Depends(get_db)
):
    """
    Register a new user with WebAuthn passkey.
    Automatically creates default payment card (5123 1212 2232 5678).
    This chat backend acts as the Credentials Provider in AP2.
    """
    # Check if user already exists
    result = await session.execute(
        select(User).where(User.email == registration.email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=400, detail="User already registered")

    # Verify WebAuthn registration
    verification = webauthn_verifier.verify_registration(
        client_data_json=registration.client_data_json,
        attestation_object=registration.attestation_object,
        challenge=registration.challenge
    )

    if not verification.get("valid"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid WebAuthn registration: {verification.get('error', 'Unknown error')}"
        )

    # Create user
    user_id = str(uuid.uuid4())
    new_user = User(
        id=user_id,
        email=registration.email,
        display_name=registration.display_name,
        passkey_credential_id=verification["credential_id"],
        passkey_public_key=verification["public_key"]
    )

    session.add(new_user)

    # Create default payment card (5123 1212 2232 5678 - Mastercard test card)
    default_card_number = "5123 1212 2232 5678"
    encrypted_card = card_encryptor.encrypt_card_number(default_card_number)
    last_four = card_encryptor.get_last_four(default_card_number)
    card_network = card_encryptor.detect_card_network(default_card_number)

    card_id = str(uuid.uuid4())
    payment_card = PaymentCard(
        id=card_id,
        user_id=user_id,
        user_email=registration.email,
        card_number_encrypted=encrypted_card,
        card_last_four=last_four,
        card_network=card_network,
        card_holder_name=registration.display_name,
        expiry_month=12,
        expiry_year=2028,
        is_default=True
    )

    session.add(payment_card)
    await session.commit()
    await session.refresh(new_user)
    await session.refresh(payment_card)

    logger.info(f"User registered: {registration.email} with default card ending {last_four}")

    return UserRegistrationResponse(
        user_id=user_id,
        email=registration.email,
        display_name=registration.display_name,
        credential_id=verification["credential_id"],
        default_card=payment_card.to_dict(masked=True)
    )


@app.post("/api/auth/verify-passkey")
async def verify_passkey(
    verification: PasskeyVerification,
    session: AsyncSession = Depends(get_db)
):
    """Verify passkey authentication for payment mandate signing."""
    logger.info(f"Verifying passkey for {verification.email}, credential_id: {verification.credential_id[:20]}...")

    # First, try to find user by email only
    result = await session.execute(
        select(User).where(User.email == verification.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.error(f"User not found for email: {verification.email}")
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f"Found user: {user.email}, stored credential_id: {user.passkey_credential_id[:20] if user.passkey_credential_id else 'None'}...")

    # Check if credential ID matches
    if user.passkey_credential_id != verification.credential_id:
        logger.warning(f"Credential ID mismatch for {user.email}")
        # Still proceed with verification but log the mismatch

    # Verify authentication
    is_valid = webauthn_verifier.verify_authentication(
        credential_id=verification.credential_id,
        client_data_json=verification.client_data_json,
        authenticator_data=verification.authenticator_data,
        signature=verification.signature,
        public_key=user.passkey_public_key,
        challenge=verification.challenge
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid authentication")

    # Generate a signature for the payment mandate (base64 encoded signature)
    return {
        "valid": True,
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "signature": verification.signature  # Return the passkey signature for mandate signing
    }


# ============================================================================
# Payment Card Endpoints (Credentials Provider)
# ============================================================================

@app.get("/api/payment/cards", response_model=List[PaymentCardResponse])
async def list_user_cards(
    user_email: str,
    session: AsyncSession = Depends(get_db)
):
    """List all payment cards for a user (masked)."""
    result = await session.execute(
        select(PaymentCard).where(
            PaymentCard.user_email == user_email,
            PaymentCard.is_active == True
        )
    )
    cards = result.scalars().all()

    return [
        PaymentCardResponse(
            id=card.id,
            user_email=card.user_email,
            card_last_four=card.card_last_four,
            card_network=card.card_network,
            card_holder_name=card.card_holder_name,
            is_default=card.is_default,
            created_at=card.created_at.isoformat() if card.created_at else ""
        )
        for card in cards
    ]


@app.get("/api/payment/cards/default", response_model=PaymentCardResponse)
async def get_default_card(
    user_email: str,
    session: AsyncSession = Depends(get_db)
):
    """Get user's default payment card (masked)."""
    result = await session.execute(
        select(PaymentCard).where(
            PaymentCard.user_email == user_email,
            PaymentCard.is_default == True,
            PaymentCard.is_active == True
        )
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="No default card found")

    return PaymentCardResponse(
        id=card.id,
        user_email=card.user_email,
        card_last_four=card.card_last_four,
        card_network=card.card_network,
        card_holder_name=card.card_holder_name,
        is_default=card.is_default,
        created_at=card.created_at.isoformat() if card.created_at else ""
    )


# ============================================================================
# AP2 Payment Mandate Endpoints (Consumer Agent)
# ============================================================================

def get_ap2_client() -> AP2Client:
    """Get AP2 client instance."""
    return app.state.ap2_client


class PrepareCheckoutRequest(BaseModel):
    """Request to prepare checkout with payment mandate."""
    session_id: str
    user_email: str


class PrepareCheckoutResponse(BaseModel):
    """Response with unsigned payment mandate."""
    mandate_id: str
    mandate_data: Dict[str, Any]
    cart_total: float
    cart_items: List[Dict[str, Any]]
    default_card: Dict[str, Any]


class ConfirmCheckoutRequest(BaseModel):
    """Request to confirm checkout with signed mandate."""
    mandate_id: str
    user_signature: str  # WebAuthn signature
    user_email: str


class ConfirmCheckoutResponse(BaseModel):
    """Response after payment processing."""
    status: str  # "success", "otp_required", "failed"
    receipt: Optional[Dict[str, Any]] = None
    otp_challenge: Optional[Dict[str, Any]] = None
    message: str


class VerifyOTPRequest(BaseModel):
    """Request to verify OTP and complete payment."""
    mandate_id: str
    otp_code: str
    user_email: str


@app.post("/api/payment/prepare-checkout", response_model=PrepareCheckoutResponse)
async def prepare_checkout(
    request: PrepareCheckoutRequest,
    agent: EnhancedBusinessAgent = Depends(get_agent),
    ap2_client: AP2Client = Depends(get_ap2_client),
    session: AsyncSession = Depends(get_db)
):
    """
    Prepare checkout - create unsigned payment mandate.
    Returns cart info and default card for user to review before signing.
    """
    # Get cart from session
    cart_info = agent.get_cart(request.session_id)
    if not cart_info or not cart_info.get("cart") or cart_info["item_count"] == 0:
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Get user's default card
    result = await session.execute(
        select(PaymentCard).where(
            PaymentCard.user_email == request.user_email,
            PaymentCard.is_default == True,
            PaymentCard.is_active == True
        )
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="No payment card found. Please register first.")

    # Create payment mandate (unsigned)
    mandate = ap2_client.create_payment_mandate(
        cart_data=cart_info,
        payment_card=card.to_dict(masked=True),
        user_email=request.user_email
    )

    # Store mandate in database (pending signature)
    mandate_id = mandate["payment_mandate_contents"]["payment_mandate_id"]
    db_mandate = PaymentMandate(
        id=mandate_id,
        user_id=card.user_id,
        user_email=request.user_email,
        cart_id=request.session_id,
        payment_card_id=card.id,
        total_amount=cart_info["total"],
        currency="USD",
        mandate_data=json.dumps(mandate),
        status="pending"
    )

    session.add(db_mandate)
    await session.commit()

    logger.info(f"Prepared checkout for {request.user_email}: mandate {mandate_id}")

    # Transform cart items to match frontend format
    cart_items = [
        {
            "id": item["product_id"],
            "sku": item.get("sku", item["product_id"]),
            "title": item["name"],
            "price": item["price"],
            "quantity": item["quantity"],
            "image_url": item.get("image_url")
        }
        for item in cart_info["cart"]
    ]

    return PrepareCheckoutResponse(
        mandate_id=mandate_id,
        mandate_data=mandate,
        cart_total=cart_info["total"],
        cart_items=cart_items,
        default_card=card.to_dict(masked=True)
    )


@app.post("/api/payment/confirm-checkout", response_model=ConfirmCheckoutResponse)
async def confirm_checkout(
    request: ConfirmCheckoutRequest,
    ap2_client: AP2Client = Depends(get_ap2_client),
    session: AsyncSession = Depends(get_db)
):
    """
    Confirm checkout - sign mandate and send to merchant for payment processing.
    """
    # Get mandate from database
    result = await session.execute(
        select(PaymentMandate).where(
            PaymentMandate.id == request.mandate_id,
            PaymentMandate.user_email == request.user_email
        )
    )
    db_mandate = result.scalar_one_or_none()

    if not db_mandate:
        raise HTTPException(status_code=404, detail="Payment mandate not found")

    if db_mandate.status != "pending":
        raise HTTPException(status_code=400, detail=f"Mandate already {db_mandate.status}")

    # Add signature to mandate
    mandate_data = json.loads(db_mandate.mandate_data)
    mandate_data["user_authorization"] = request.user_signature

    # Update mandate in database
    db_mandate.user_signature = request.user_signature
    db_mandate.status = "signed"
    db_mandate.signed_at = datetime.utcnow()
    db_mandate.mandate_data = json.dumps(mandate_data)
    await session.commit()

    # Send to merchant's AP2 payment processor
    try:
        receipt = await ap2_client.send_payment_mandate(mandate_data)

        # Check if OTP challenge
        otp_challenge = ap2_client.extract_otp_challenge(receipt)
        if otp_challenge:
            db_mandate.status = "otp_required"
            await session.commit()

            logger.info(f"OTP challenge for mandate {request.mandate_id}")
            return ConfirmCheckoutResponse(
                status="otp_required",
                otp_challenge=otp_challenge,
                message="OTP verification required. Please enter the code sent to your email."
            )

        # Payment successful
        db_mandate.status = "completed"
        db_mandate.completed_at = datetime.utcnow()

        # Store receipt
        receipt_id = f"RCP-{uuid.uuid4().hex[:12].upper()}"
        db_receipt = PaymentReceipt(
            id=receipt_id,
            payment_mandate_id=request.mandate_id,
            confirmation_id=receipt.get("payment_id", "UNKNOWN"),
            amount=receipt["amount"]["value"],
            currency=receipt["amount"]["currency"],
            status="success",
            receipt_data=json.dumps(receipt)
        )

        session.add(db_receipt)
        await session.commit()

        logger.info(f"Payment successful for mandate {request.mandate_id}")
        return ConfirmCheckoutResponse(
            status="success",
            receipt=receipt,
            message="Payment completed successfully!"
        )

    except Exception as e:
        db_mandate.status = "failed"
        await session.commit()

        logger.error(f"Payment failed for mandate {request.mandate_id}: {e}")
        return ConfirmCheckoutResponse(
            status="failed",
            message=f"Payment failed: {str(e)}"
        )


@app.post("/api/payment/verify-otp", response_model=ConfirmCheckoutResponse)
async def verify_otp_and_complete(
    request: VerifyOTPRequest,
    ap2_client: AP2Client = Depends(get_ap2_client),
    session: AsyncSession = Depends(get_db)
):
    """
    Verify OTP and complete payment.
    """
    # Get mandate
    result = await session.execute(
        select(PaymentMandate).where(
            PaymentMandate.id == request.mandate_id,
            PaymentMandate.user_email == request.user_email
        )
    )
    db_mandate = result.scalar_one_or_none()

    if not db_mandate or db_mandate.status != "otp_required":
        raise HTTPException(status_code=400, detail="Invalid mandate state")

    # Get mandate data
    mandate_data = json.loads(db_mandate.mandate_data)

    # Send OTP to merchant
    try:
        receipt = await ap2_client.verify_otp_and_process(mandate_data, request.otp_code)

        # Check status
        payment_status = receipt.get("payment_status", {})
        if "merchant_confirmation_id" in payment_status:
            # Success
            db_mandate.status = "completed"
            db_mandate.completed_at = datetime.utcnow()

            # Store receipt
            receipt_id = f"RCP-{uuid.uuid4().hex[:12].upper()}"
            db_receipt = PaymentReceipt(
                id=receipt_id,
                payment_mandate_id=request.mandate_id,
                confirmation_id=receipt.get("payment_id", "UNKNOWN"),
                amount=receipt["amount"]["value"],
                currency=receipt["amount"]["currency"],
                status="success",
                receipt_data=json.dumps(receipt)
            )

            session.add(db_receipt)
            await session.commit()

            logger.info(f"OTP verified, payment successful for mandate {request.mandate_id}")
            return ConfirmCheckoutResponse(
                status="success",
                receipt=receipt,
                message="Payment completed successfully!"
            )
        else:
            # Failed
            db_mandate.status = "failed"
            await session.commit()

            logger.warning(f"OTP verification failed for mandate {request.mandate_id}")
            return ConfirmCheckoutResponse(
                status="failed",
                message="Invalid OTP code"
            )

    except Exception as e:
        logger.error(f"OTP verification error for mandate {request.mandate_id}: {e}")
        return ConfirmCheckoutResponse(
            status="failed",
            message=f"OTP verification failed: {str(e)}"
        )


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
