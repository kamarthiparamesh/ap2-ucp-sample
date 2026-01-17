"""
Merchant Backend - UCP Product Service
Exposes product catalog via UCP-compliant REST API
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uvicorn
import json
import os
from datetime import datetime
from dotenv import load_dotenv

from database import db_manager, Product
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from merchant_payment_agent import MerchantPaymentAgent
from ap2_types import PaymentMandate as AP2PaymentMandate, PaymentReceipt as AP2PaymentReceipt, OTPVerification

# Load environment variables
load_dotenv()


# ============================================================================
# Pydantic Models
# ============================================================================

class ProductCreate(BaseModel):
    """Model for creating a new product."""
    sku: str
    name: str
    description: Optional[str] = None
    price: float
    currency: str = "USD"
    category: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[List[str]] = None
    availability: str = "https://schema.org/InStock"
    condition: str = "https://schema.org/NewCondition"
    gtin: Optional[str] = None
    mpn: Optional[str] = None


class ProductUpdate(BaseModel):
    """Model for updating a product."""
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[List[str]] = None
    availability: Optional[str] = None
    condition: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    """Product response model."""
    id: str
    sku: str
    name: str
    description: Optional[str]
    price: float
    currency: str
    category: Optional[str]
    brand: Optional[str]
    image_url: Optional[str]
    availability: str
    condition: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UCPProductItem(BaseModel):
    """UCP-compliant product item."""
    id: str
    title: str
    price: int  # Price in cents
    image_url: Optional[str] = None
    description: Optional[str] = None


class UCPSearchResponse(BaseModel):
    """UCP search response."""
    items: List[UCPProductItem]
    total: int


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    # Startup
    db_manager.init_db()

    # Seed database with sample products if empty
    await seed_initial_products()

    # Initialize AP2 Merchant Payment Agent
    ollama_url = os.getenv("OLLAMA_URL", "http://192.168.86.41:11434")
    ollama_model = os.getenv("AP2_MERCHANT_MODEL", "qwen2.5:8b")
    app.state.payment_agent = MerchantPaymentAgent(
        ollama_url=ollama_url,
        model_name=ollama_model
    )

    yield

    # Shutdown (cleanup if needed)
    pass


async def seed_initial_products():
    """Seed database with initial products if empty."""
    async for session in db_manager.get_session():
        result = await session.execute(select(Product))
        existing = result.scalars().first()

        if not existing:
            sample_products = [
                Product(
                    id="PROD-001",
                    sku="BISC-001",
                    name="Chocochip Cookies",
                    description="Delicious chocolate chip cookies, freshly baked",
                    price=4.99,
                    category="Bakery/Cookies",
                    brand="HomeBaked",
                    image_url=json.dumps(["https://images.unsplash.com/photo-1499636136210-6f4ee915583e?w=400&h=400&fit=crop&q=80"]),
                ),
                Product(
                    id="PROD-002",
                    sku="STRAW-001",
                    name="Fresh Strawberries",
                    description="Sweet and juicy fresh strawberries",
                    price=4.49,
                    category="Produce/Fruits",
                    brand="FarmFresh",
                    image_url=json.dumps(["https://images.unsplash.com/photo-1464965911861-746a04b4bca6?w=400&h=400&fit=crop&q=80"]),
                ),
                Product(
                    id="PROD-003",
                    sku="CHIPS-001",
                    name="Classic Potato Chips",
                    description="Crispy salted potato chips",
                    price=3.79,
                    category="Snacks/Chips",
                    brand="CrunchTime",
                    image_url=json.dumps(["https://images.unsplash.com/photo-1566478989037-eec170784d0b?w=400&h=400&fit=crop&q=80"]),
                ),
                Product(
                    id="PROD-004",
                    sku="SW-CHIPS-001",
                    name="Baked Sweet Potato Chips",
                    description="Healthy baked sweet potato chips",
                    price=4.79,
                    category="Snacks/Chips",
                    brand="HealthyChoice",
                    image_url=json.dumps(["https://images.unsplash.com/photo-1626200655629-cbee9dc8f42e?w=400&h=400&fit=crop&q=80"]),
                ),
                Product(
                    id="PROD-005",
                    sku="O-COOKIES-001",
                    name="Classic Oat Cookies",
                    description="Wholesome oatmeal cookies with raisins",
                    price=5.99,
                    category="Bakery/Cookies",
                    brand="HomeBaked",
                    image_url=json.dumps(["https://images.unsplash.com/photo-1558961363-fa8fdf82db35?w=400&h=400&fit=crop&q=80"]),
                ),
                Product(
                    id="PROD-006",
                    sku="NUTRIBAR-001",
                    name="Nutri-Bar",
                    description="Nutritious energy bar with nuts and fruits",
                    price=2.99,
                    category="Snacks/Bars",
                    brand="EnergyPlus",
                    image_url=json.dumps(["https://images.unsplash.com/photo-1604480133435-25b9560f4294?w=400&h=400&fit=crop&q=80"]),
                ),
            ]

            session.add_all(sample_products)
            await session.commit()


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Merchant Backend API",
    description="UCP-compliant product catalog and merchant portal",
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

async def get_db() -> AsyncSession:
    """Get database session."""
    async for session in db_manager.get_session():
        yield session


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - provides API information."""
    return {
        "service": "Merchant Backend API",
        "version": "1.0.0",
        "description": "UCP-compliant product catalog and merchant portal",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "ucp": {
                "discovery": "GET /.well-known/ucp",
                "product_search": "GET /ucp/products/search"
            },
            "api": {
                "list_products": "GET /api/products",
                "get_product": "GET /api/products/{product_id}",
                "create_product": "POST /api/products",
                "update_product": "PUT /api/products/{product_id}",
                "delete_product": "DELETE /api/products/{product_id}"
            }
        },
        "frontend_url": "http://localhost:3001",
        "ucp_compliant": True,
        "status": "running"
    }


# ============================================================================
# UCP Endpoints (/.well-known/ucp)
# ============================================================================

@app.get("/.well-known/ucp")
async def get_ucp_profile():
    """
    UCP Discovery Endpoint
    Returns merchant capabilities and service endpoints
    """
    merchant_url = os.getenv("MERCHANT_URL", "http://localhost:8451")

    return {
        "ucp": {
            "version": "2026-01-11",
            "services": {
                "dev.ucp.shopping": {
                    "version": "2026-01-11",
                    "spec": "https://ucp.dev/specs/shopping",
                    "rest": {
                        "schema": "https://ucp.dev/services/shopping/openapi.json",
                        "endpoint": merchant_url
                    }
                }
            },
            "capabilities": [
                {
                    "name": "dev.ucp.shopping.product_search",
                    "version": "2026-01-11",
                    "spec": "https://ucp.dev/specs/shopping/product_search",
                    "schema": "https://ucp.dev/schemas/shopping/product_search.json"
                }
            ]
        },
        "merchant": {
            "id": os.getenv("MERCHANT_ID", "merchant-001"),
            "name": os.getenv("MERCHANT_NAME", "Enhanced Business Store"),
            "url": merchant_url
        }
    }


# ============================================================================
# UCP Product Search Endpoint
# ============================================================================

@app.get("/ucp/products/search", response_model=UCPSearchResponse)
async def ucp_search_products(
    q: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
    session: AsyncSession = Depends(get_db)
):
    """
    UCP-compliant product search endpoint.
    This endpoint can be discovered and called by UCP clients.
    """
    query = select(Product).where(Product.is_active == True)

    if q:
        search_term = f"%{q.lower()}%"
        query = query.where(
            (Product.name.ilike(search_term)) |
            (Product.description.ilike(search_term)) |
            (Product.category.ilike(search_term))
        )

    if category:
        query = query.where(Product.category.ilike(f"%{category}%"))

    query = query.limit(limit)
    result = await session.execute(query)
    products = result.scalars().all()

    # Convert to UCP format (prices in cents)
    items = [
        UCPProductItem(
            id=p.id,
            title=p.name,
            price=int(p.price * 100),  # Convert to cents
            image_url=p.image_url,
            description=p.description
        )
        for p in products
    ]

    return UCPSearchResponse(
        items=items,
        total=len(items)
    )


# ============================================================================
# Merchant Portal - Product Management Endpoints
# ============================================================================

@app.get("/api/products", response_model=List[ProductResponse])
async def list_products(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    session: AsyncSession = Depends(get_db)
):
    """
    List all products in the catalog.
    Merchant portal endpoint for viewing products.
    """
    query = select(Product)
    if active_only:
        query = query.where(Product.is_active == True)

    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    products = result.scalars().all()

    return [
        ProductResponse(
            id=p.id,
            sku=p.sku,
            name=p.name,
            description=p.description,
            price=p.price,
            currency=p.currency,
            category=p.category,
            brand=p.brand,
            image_url=p.image_url,
            availability=p.availability,
            condition=p.condition,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in products
    ]


@app.get("/api/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get a specific product by ID."""
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return ProductResponse(
        id=product.id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        price=product.price,
        currency=product.currency,
        category=product.category,
        brand=product.brand,
        image_url=product.image_url,
        availability=product.availability,
        condition=product.condition,
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at
    )


@app.post("/api/products", response_model=ProductResponse, status_code=201)
async def create_product(
    product: ProductCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new product.
    Merchant portal endpoint.
    """
    # Check if SKU already exists
    result = await session.execute(
        select(Product).where(Product.sku == product.sku)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")

    # Generate product ID
    import time
    product_id = f"PROD-{int(time.time())}"

    db_product = Product(
        id=product_id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        price=product.price,
        currency=product.currency,
        category=product.category,
        brand=product.brand,
        image_url=json.dumps(product.image_url or []),
        availability=product.availability,
        condition=product.condition,
        gtin=product.gtin,
        mpn=product.mpn
    )

    session.add(db_product)
    await session.commit()
    await session.refresh(db_product)

    return ProductResponse(
        id=db_product.id,
        sku=db_product.sku,
        name=db_product.name,
        description=db_product.description,
        price=db_product.price,
        currency=db_product.currency,
        category=db_product.category,
        brand=db_product.brand,
        image_url=db_product.image_url,
        availability=db_product.availability,
        condition=db_product.condition,
        is_active=db_product.is_active,
        created_at=db_product.created_at,
        updated_at=db_product.updated_at
    )


@app.put("/api/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    product_update: ProductUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Update an existing product.
    Merchant portal endpoint.
    """
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    db_product = result.scalar_one_or_none()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Update fields
    update_data = product_update.model_dump(exclude_unset=True)

    if "image_url" in update_data and update_data["image_url"] is not None:
        update_data["image_url"] = json.dumps(update_data["image_url"])

    for field, value in update_data.items():
        setattr(db_product, field, value)

    db_product.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(db_product)

    return ProductResponse(
        id=db_product.id,
        sku=db_product.sku,
        name=db_product.name,
        description=db_product.description,
        price=db_product.price,
        currency=db_product.currency,
        category=db_product.category,
        brand=db_product.brand,
        image_url=db_product.image_url,
        availability=db_product.availability,
        condition=db_product.condition,
        is_active=db_product.is_active,
        created_at=db_product.created_at,
        updated_at=db_product.updated_at
    )


@app.delete("/api/products/{product_id}")
async def delete_product(
    product_id: str,
    hard_delete: bool = False,
    session: AsyncSession = Depends(get_db)
):
    """
    Delete a product (soft delete by default).
    Merchant portal endpoint.
    """
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    db_product = result.scalar_one_or_none()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    if hard_delete:
        await session.delete(db_product)
    else:
        db_product.is_active = False
        db_product.updated_at = datetime.utcnow()

    await session.commit()

    return {"message": "Product deleted successfully", "product_id": product_id}


# ============================================================================
# AP2 Payment Processing Endpoints (Merchant Agent)
# ============================================================================

def get_payment_agent() -> MerchantPaymentAgent:
    """Get payment agent instance."""
    return app.state.payment_agent


@app.post("/ap2/payment/process", response_model=AP2PaymentReceipt)
async def process_payment_mandate(
    mandate: AP2PaymentMandate,
    payment_agent: MerchantPaymentAgent = Depends(get_payment_agent)
):
    """
    Process AP2 payment mandate from consumer (chat backend).

    Flow:
    1. Validate mandate signature
    2. Check if OTP challenge needed
    3. Process payment or return OTP challenge
    """
    # Check if OTP challenge should be raised
    if payment_agent.should_raise_otp_challenge(mandate):
        challenge = payment_agent.create_otp_challenge(mandate)
        # Return as error status with OTP info
        return AP2PaymentReceipt(
            payment_mandate_id=mandate.payment_mandate_contents.payment_mandate_id,
            timestamp=datetime.utcnow().isoformat(),
            payment_id="PENDING-OTP",
            amount=mandate.payment_mandate_contents.payment_details_total.amount,
            payment_status=PaymentReceiptError(
                error_message=f"OTP_REQUIRED:{challenge.message}"
            ),
            payment_method_details={"otp_challenge": challenge.dict()}
        )

    # Process payment
    receipt = payment_agent.process_payment(mandate)
    return receipt


@app.post("/ap2/payment/verify-otp", response_model=AP2PaymentReceipt)
async def verify_otp_and_process(
    mandate: AP2PaymentMandate,
    otp_verification: OTPVerification,
    payment_agent: MerchantPaymentAgent = Depends(get_payment_agent)
):
    """
    Verify OTP and process payment.
    Called after user provides OTP code.
    """
    # Verify OTP
    if not payment_agent.verify_otp(
        otp_verification.payment_mandate_id,
        otp_verification.otp_code
    ):
        return AP2PaymentReceipt(
            payment_mandate_id=mandate.payment_mandate_contents.payment_mandate_id,
            timestamp=datetime.utcnow().isoformat(),
            payment_id="ERR-INVALID-OTP",
            amount=mandate.payment_mandate_contents.payment_details_total.amount,
            payment_status=PaymentReceiptFailure(
                failure_message="Invalid OTP code"
            )
        )

    # OTP verified, process payment
    receipt = payment_agent.process_payment(mandate)
    return receipt


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "merchant-backend",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8451))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
