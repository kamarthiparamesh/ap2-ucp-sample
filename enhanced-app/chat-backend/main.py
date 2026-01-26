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
from database import db_manager, User, PaymentCard, PaymentMandate, PaymentReceipt, MastercardAuthenticationChallenge
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from payment_utils import (
    card_encryptor,
    webauthn_verifier,
    token_generator,
    otp_manager
)
from ap2_client import AP2Client
from mastercard_client import MastercardClient
from loyalty_client import LoyaltyClient

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
    products: Optional[List[Dict[str, Any]]] = None


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
    credential_id: str  # WebAuthn credential ID from browser
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

    # Initialize Loyalty client (for A2A loyalty communication)
    app.state.loyalty_client = LoyaltyClient(merchant_url)
    logger.info("Loyalty client initialized")

    # Initialize Mastercard client (for tokenization and authentication)
    app.state.mastercard_client = MastercardClient(sandbox=True)
    if app.state.mastercard_client.enabled:
        logger.info("Mastercard API integration enabled")
    else:
        logger.warning("Mastercard API integration disabled (credentials not configured)")

    yield

    # Shutdown
    await app.state.agent.cleanup()
    await app.state.ap2_client.cleanup()
    await app.state.loyalty_client.cleanup()
    if app.state.mastercard_client.enabled:
        await app.state.mastercard_client.cleanup()
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


def get_mastercard_client() -> MastercardClient:
    """Get Mastercard API client instance."""
    return app.state.mastercard_client


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


@app.get("/api/products")
async def get_products(
    query: str = None,
    limit: int = 20,
    agent: EnhancedBusinessAgent = Depends(get_agent)
):
    """
    Get products via UCP from merchant backend.
    Frontend should use this endpoint instead of calling merchant directly.
    """
    products = await agent.search_products(query=query, limit=limit)

    # Transform to include SKU (use product ID as SKU if not available)
    for product in products:
        if 'sku' not in product:
            product['sku'] = product['id']

    return {"products": products}


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
        status=result["status"],
        products=result.get("products")
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
        "currency": "SGD",
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
        currency="SGD",
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
    session: AsyncSession = Depends(get_db),
    mastercard: MastercardClient = Depends(get_mastercard_client)
):
    """
    Register a new user with WebAuthn passkey.
    Automatically creates default payment card (5123 1212 2232 5678).
    Tokenizes card with Mastercard API if enabled.
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
        challenge=registration.challenge,
        credential_id=registration.credential_id
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

    # Tokenize card with Mastercard API if enabled
    if mastercard.enabled and card_network == "mastercard":
        try:
            logger.info(f"Tokenizing card for user {registration.email} with Mastercard API")
            token_response = await mastercard.tokenization.tokenize_card(
                card_number=default_card_number.replace(" ", ""),
                expiry_month=12,
                expiry_year=2028,
                cardholder_name=registration.display_name
            )

            # Store Mastercard token data
            payment_card.mastercard_token = token_response["token"]
            payment_card.mastercard_token_ref = token_response["token_unique_reference"]
            payment_card.mastercard_token_assurance = token_response["token_assurance_level"]
            payment_card.tokenization_date = datetime.utcnow()
            payment_card.is_tokenized = True

            logger.info(f"Card tokenized successfully for {registration.email}: {token_response['token_unique_reference'][:20]}...")
        except Exception as e:
            logger.error(f"Failed to tokenize card with Mastercard API: {e}")
            logger.info("Continuing with encrypted card storage only")
            # Continue without tokenization - fall back to encrypted storage

    session.add(payment_card)
    await session.commit()
    await session.refresh(new_user)
    await session.refresh(payment_card)

    logger.info(f"User registered: {registration.email} with default card ending {last_four} (tokenized: {payment_card.is_tokenized})")

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
    promocode: Optional[str] = None  # Optional promocode/coupon


class PrepareCheckoutResponse(BaseModel):
    """Response with unsigned payment mandate."""
    mandate_id: str
    mandate_data: Dict[str, Any]
    cart_total: float
    cart_items: List[Dict[str, Any]]
    default_card: Dict[str, Any]
    promocode: Optional[Dict[str, Any]] = None  # Applied promocode info
    promocode_error: Optional[str] = None  # Promocode validation error


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
    Prepare checkout - create UCP checkout session and payment mandate.
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

    # Transform cart items for UCP checkout session
    cart_items = [
        {
            "id": item["product_id"],
            "sku": item.get("sku", item["product_id"]),
            "name": item["name"],
            "quantity": item["quantity"],
            "price": item["price"]
        }
        for item in cart_info["cart"]
    ]

    # Create UCP checkout session
    checkout_session = await ap2_client.create_checkout_session(
        cart_items=cart_items,
        buyer_email=request.user_email,
        promocode=request.promocode if request.promocode else None
    )

    # Get final total from checkout session (includes any promocode discount)
    final_total = checkout_session.get("totals", {}).get("total", cart_info["total"])

    # Update cart_info with discounted total if promocode was applied
    updated_cart_info = cart_info.copy()
    updated_cart_info["total"] = final_total

    # Create payment mandate (unsigned) for AP2 with updated total
    mandate = ap2_client.create_payment_mandate(
        cart_data=updated_cart_info,
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
        total_amount=final_total,  # Use discounted total
        currency="SGD",
        mandate_data=json.dumps(mandate),
        checkout_session_id=checkout_session["id"],  # Store UCP session ID
        status="pending"
    )

    session.add(db_mandate)
    await session.commit()

    logger.info(f"Prepared checkout for {request.user_email}: UCP session {checkout_session['id']}, mandate {mandate_id}")

    # Transform cart items to match frontend format
    frontend_cart_items = [
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

    # Extract promocode info from checkout session
    promocode_info = checkout_session.get("promocode")
    promocode_error = checkout_session.get("promocode_error")

    return PrepareCheckoutResponse(
        mandate_id=mandate_id,
        mandate_data=mandate,
        cart_total=final_total,
        cart_items=frontend_cart_items,
        default_card=card.to_dict(masked=True),
        promocode=promocode_info,
        promocode_error=promocode_error
    )


@app.post("/api/payment/confirm-checkout", response_model=ConfirmCheckoutResponse)
async def confirm_checkout(
    request: ConfirmCheckoutRequest,
    ap2_client: AP2Client = Depends(get_ap2_client),
    mastercard: MastercardClient = Depends(get_mastercard_client),
    session: AsyncSession = Depends(get_db)
):
    """
    Confirm checkout - sign mandate and send to merchant for payment processing.
    Optionally uses Mastercard authentication if enabled.
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

    # Get payment card to check if tokenized
    card_result = await session.execute(
        select(PaymentCard).where(PaymentCard.id == db_mandate.payment_card_id)
    )
    payment_card = card_result.scalar_one_or_none()

    # Mastercard Authentication (if enabled and card is tokenized)
    if mastercard.enabled and payment_card and payment_card.is_tokenized:
        try:
            logger.info(f"Initiating Mastercard authentication for mandate {request.mandate_id}")

            # Initiate authentication with Mastercard
            auth_response = await mastercard.authentication.initiate_authentication(
                token=payment_card.mastercard_token_ref,
                amount=db_mandate.total_amount,
                currency=db_mandate.currency,
                merchant_id=os.getenv("MERCHANT_ID", "merchant-001"),
                transaction_id=db_mandate.checkout_session_id
            )

            # Store authentication challenge
            if auth_response.get("authentication_required"):
                challenge_id = str(uuid.uuid4())
                auth_challenge = MastercardAuthenticationChallenge(
                    id=challenge_id,
                    payment_mandate_id=request.mandate_id,
                    challenge_id=auth_response["challenge_id"],
                    transaction_id=db_mandate.checkout_session_id,
                    authentication_method=auth_response["authentication_method"],
                    status="pending",
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(minutes=5),
                    raw_response=json.dumps(auth_response.get("raw_response", {}))
                )
                session.add(auth_challenge)

                # Update mandate status
                db_mandate.status = "mastercard_auth_required"
                await session.commit()

                logger.info(f"Mastercard authentication required: {auth_response['authentication_method']}")

                return ConfirmCheckoutResponse(
                    status="mastercard_auth_required",
                    otp_challenge={
                        "challenge_id": challenge_id,
                        "authentication_method": auth_response["authentication_method"],
                        "message": "Mastercard authentication required. Please complete authentication."
                    },
                    message=f"Mastercard {auth_response['authentication_method']} authentication required"
                )
            else:
                logger.info(f"Mastercard authentication approved automatically for mandate {request.mandate_id}")

        except Exception as e:
            logger.error(f"Mastercard authentication error: {e}")
            logger.info("Continuing with standard payment flow")

    # Add signature to mandate
    mandate_data = json.loads(db_mandate.mandate_data)
    mandate_data["user_authorization"] = request.user_signature

    # Update mandate in database
    db_mandate.user_signature = request.user_signature
    db_mandate.status = "signed"
    db_mandate.signed_at = datetime.utcnow()
    db_mandate.mandate_data = json.dumps(mandate_data)
    await session.commit()

    # UCP Flow: Update checkout session with mandate and complete
    try:
        # Step 1: Update UCP checkout session with AP2 mandate
        await ap2_client.update_checkout_with_mandate(
            session_id=db_mandate.checkout_session_id,
            mandate=mandate_data,
            user_signature=request.user_signature
        )

        # Step 2: Complete UCP checkout
        completion_result = await ap2_client.complete_checkout(
            session_id=db_mandate.checkout_session_id
        )

        # Check if OTP challenge
        otp_challenge = ap2_client.extract_otp_challenge(completion_result)
        if otp_challenge:
            db_mandate.status = "otp_required"
            await session.commit()

            logger.info(f"OTP challenge for UCP checkout {db_mandate.checkout_session_id}")
            return ConfirmCheckoutResponse(
                status="otp_required",
                otp_challenge=otp_challenge,
                message="OTP verification required. Please enter the code sent to your email."
            )

        # Payment successful
        receipt = completion_result.get("receipt", {})
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

        logger.info(f"Payment successful via UCP for checkout {db_mandate.checkout_session_id}")
        return ConfirmCheckoutResponse(
            status="success",
            receipt=receipt,
            message="Payment completed successfully!"
        )

    except Exception as e:
        db_mandate.status = "failed"
        await session.commit()

        logger.error(f"Payment failed for UCP checkout {db_mandate.checkout_session_id}: {e}")
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

    # Complete UCP checkout with OTP
    try:
        completion_result = await ap2_client.complete_checkout(
            session_id=db_mandate.checkout_session_id,
            otp_code=request.otp_code
        )

        # Check status
        if completion_result.get("status") == "success":
            receipt = completion_result.get("receipt", {})

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

            logger.info(f"OTP verified via UCP, payment successful for checkout {db_mandate.checkout_session_id}")
            return ConfirmCheckoutResponse(
                status="success",
                receipt=receipt,
                message="Payment completed successfully!"
            )
        else:
            # Failed
            db_mandate.status = "failed"
            await session.commit()

            logger.warning(f"OTP verification failed for UCP checkout {db_mandate.checkout_session_id}")
            return ConfirmCheckoutResponse(
                status="failed",
                message="Invalid OTP code"
            )

    except Exception as e:
        logger.error(f"OTP verification error for UCP checkout {db_mandate.checkout_session_id}: {e}")
        return ConfirmCheckoutResponse(
            status="failed",
            message=f"OTP verification failed: {str(e)}"
        )


class VerifyMastercardAuthRequest(BaseModel):
    """Request to verify Mastercard authentication challenge."""
    challenge_id: str
    verification_code: str
    mandate_id: str
    user_email: str


@app.post("/api/payment/verify-mastercard-auth", response_model=ConfirmCheckoutResponse)
async def verify_mastercard_authentication(
    request: VerifyMastercardAuthRequest,
    mastercard: MastercardClient = Depends(get_mastercard_client),
    ap2_client: AP2Client = Depends(get_ap2_client),
    session: AsyncSession = Depends(get_db)
):
    """
    Verify Mastercard authentication challenge and complete payment.
    """
    if not mastercard.enabled:
        raise HTTPException(status_code=400, detail="Mastercard authentication not enabled")

    # Get authentication challenge
    result = await session.execute(
        select(MastercardAuthenticationChallenge).where(
            MastercardAuthenticationChallenge.id == request.challenge_id,
            MastercardAuthenticationChallenge.payment_mandate_id == request.mandate_id
        )
    )
    auth_challenge = result.scalar_one_or_none()

    if not auth_challenge:
        raise HTTPException(status_code=404, detail="Authentication challenge not found")

    if auth_challenge.status != "pending":
        raise HTTPException(status_code=400, detail=f"Challenge already {auth_challenge.status}")

    # Check expiry
    if datetime.utcnow() > auth_challenge.expires_at:
        auth_challenge.status = "expired"
        await session.commit()
        raise HTTPException(status_code=400, detail="Authentication challenge expired")

    # Verify with Mastercard
    try:
        logger.info(f"Verifying Mastercard authentication for challenge {request.challenge_id}")

        auth_result = await mastercard.authentication.verify_authentication(
            challenge_id=auth_challenge.challenge_id,
            verification_code=request.verification_code
        )

        if auth_result.get("verified"):
            # Authentication successful
            auth_challenge.status = "approved"
            auth_challenge.verified_at = datetime.utcnow()
            await session.commit()

            # Get mandate and proceed with payment
            mandate_result = await session.execute(
                select(PaymentMandate).where(
                    PaymentMandate.id == request.mandate_id,
                    PaymentMandate.user_email == request.user_email
                )
            )
            db_mandate = mandate_result.scalar_one_or_none()

            if not db_mandate:
                raise HTTPException(status_code=404, detail="Payment mandate not found")

            # Update mandate status
            db_mandate.status = "signed"
            db_mandate.signed_at = datetime.utcnow()

            # Get mandate data
            mandate_data = json.loads(db_mandate.mandate_data)

            # Complete UCP checkout
            await ap2_client.update_checkout_with_mandate(
                session_id=db_mandate.checkout_session_id,
                mandate=mandate_data,
                user_signature=db_mandate.user_signature
            )

            completion_result = await ap2_client.complete_checkout(
                session_id=db_mandate.checkout_session_id
            )

            # Check if standard OTP challenge (in addition to Mastercard auth)
            otp_challenge = ap2_client.extract_otp_challenge(completion_result)
            if otp_challenge:
                db_mandate.status = "otp_required"
                await session.commit()

                logger.info(f"Additional OTP required after Mastercard auth for checkout {db_mandate.checkout_session_id}")
                return ConfirmCheckoutResponse(
                    status="otp_required",
                    otp_challenge=otp_challenge,
                    message="Additional OTP verification required"
                )

            # Payment successful
            receipt = completion_result.get("receipt", {})
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

            logger.info(f"Mastercard authentication verified, payment successful for checkout {db_mandate.checkout_session_id}")
            return ConfirmCheckoutResponse(
                status="success",
                receipt=receipt,
                message="Payment completed successfully!"
            )
        else:
            # Authentication failed
            auth_challenge.status = "declined"
            auth_challenge.attempts += 1
            await session.commit()

            logger.warning(f"Mastercard authentication failed for challenge {request.challenge_id}")
            return ConfirmCheckoutResponse(
                status="failed",
                message="Authentication verification failed"
            )

    except Exception as e:
        logger.error(f"Mastercard authentication verification error: {e}")
        return ConfirmCheckoutResponse(
            status="failed",
            message=f"Verification failed: {str(e)}"
        )


# ============================================================================
# Loyalty Endpoints (Consumer Agent - communicates with Merchant via UCP A2A)
# ============================================================================

def get_loyalty_client() -> LoyaltyClient:
    """Get loyalty client instance."""
    return app.state.loyalty_client


class LoyaltyInquiryRequest(BaseModel):
    """Request to query loyalty via A2A."""
    user_email: str
    inquiry: str


@app.post("/api/loyalty/query")
async def query_loyalty_via_a2a(
    request: LoyaltyInquiryRequest,
    agent: EnhancedBusinessAgent = Depends(get_agent),
    loyalty_client: LoyaltyClient = Depends(get_loyalty_client)
):
    """
    Query loyalty program via A2A (chat backend -> merchant backend).
    Consumer agent sends inquiry to merchant agent.
    """
    try:
        # Get cart context if available
        cart_info = agent.get_cart("default")  # Use default session for now

        # Send inquiry to merchant's loyalty agent via A2A
        response = await loyalty_client.query_loyalty(
            user_email=request.user_email,
            inquiry=request.inquiry,
            context={"cart": cart_info} if cart_info else None
        )

        return response

    except Exception as e:
        logger.error(f"Loyalty query error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to query loyalty: {str(e)}")


@app.get("/api/loyalty/status")
async def get_user_loyalty_status(
    user_email: str,
    loyalty_client: LoyaltyClient = Depends(get_loyalty_client)
):
    """Get loyalty status for a user via A2A."""
    try:
        status = await loyalty_client.get_loyalty_status(user_email)
        return status

    except Exception as e:
        logger.error(f"Loyalty status error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get loyalty status: {str(e)}")


@app.post("/api/loyalty/redeem")
async def redeem_points(
    user_email: str,
    points: int,
    redemption_type: str = "discount",
    loyalty_client: LoyaltyClient = Depends(get_loyalty_client)
):
    """Redeem loyalty points via A2A."""
    try:
        result = await loyalty_client.redeem_loyalty_points(
            user_email=user_email,
            points=points,
            redemption_type=redemption_type
        )

        return result

    except Exception as e:
        logger.error(f"Loyalty redemption error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to redeem points: {str(e)}")


# ============================================================================
# Database Management Endpoints
# ============================================================================

@app.post("/api/database/reset")
async def reset_database(session: AsyncSession = Depends(get_db)):
    """
    Reset all database tables - removes all users, cards, mandates, receipts, and auth challenges.
    This is useful for testing and development.
    """
    try:
        from sqlalchemy import delete

        # Delete all records from tables (in correct order to respect foreign keys)
        await session.execute(delete(PaymentReceipt))
        await session.execute(delete(MastercardAuthenticationChallenge))
        await session.execute(delete(PaymentMandate))
        await session.execute(delete(PaymentCard))
        await session.execute(delete(User))

        await session.commit()

        logger.info("Database reset successful - all tables cleared")

        return {
            "status": "success",
            "message": "Database has been reset successfully. All users, cards, and transactions have been removed.",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        await session.rollback()
        logger.error(f"Database reset failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")


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
