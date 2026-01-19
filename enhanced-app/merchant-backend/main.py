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
import logging
from datetime import datetime
from dotenv import load_dotenv

from database import db_manager, Product, UCPRequestLog, AP2RequestLog, Promocode
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from merchant_payment_agent import MerchantPaymentAgent
from ap2_types import PaymentMandate as AP2PaymentMandate, PaymentReceipt as AP2PaymentReceipt, OTPVerification, PaymentReceiptSuccess
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse, JSONResponse
import time
from io import BytesIO
# No longer using contextvars - using request.state instead

# Load environment variables
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class ProductCreate(BaseModel):
    """Model for creating a new product."""
    sku: str
    name: str
    description: Optional[str] = None
    price: float
    currency: str = "SGD"
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

    # Seed database with sample products and promocodes if empty
    await seed_initial_data()

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


async def seed_initial_data():
    """Seed database with initial products and promocodes if empty."""
    async for session in db_manager.get_session():
        # Seed products
        result = await session.execute(select(Product))
        existing_products = result.scalars().first()

        if not existing_products:
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

        # Seed promocodes
        result = await session.execute(select(Promocode))
        existing_promocodes = result.scalars().first()

        if not existing_promocodes:
            from datetime import timedelta
            now = datetime.utcnow()

            sample_promocodes = [
                Promocode(
                    id="PROMO-001",
                    code="SAVE10",
                    description="10% off your order",
                    discount_type="percentage",
                    discount_value=10.0,
                    currency="SGD",
                    valid_from=now,
                    valid_until=now + timedelta(days=90)
                ),
                Promocode(
                    id="PROMO-002",
                    code="WELCOME5",
                    description="$5 off your first order",
                    discount_type="fixed_amount",
                    discount_value=5.0,
                    currency="SGD",
                    min_purchase_amount=20.0,
                    usage_limit=100,
                    valid_from=now,
                    valid_until=now + timedelta(days=60)
                ),
                Promocode(
                    id="PROMO-003",
                    code="FLASH20",
                    description="Flash sale - 20% off (max $10 discount)",
                    discount_type="percentage",
                    discount_value=20.0,
                    currency="SGD",
                    max_discount_amount=10.0,
                    min_purchase_amount=25.0,
                    usage_limit=50,
                    valid_from=now,
                    valid_until=now + timedelta(days=7)
                ),
            ]

            session.add_all(sample_promocodes)
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
# Request Logging Middleware
# ============================================================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log UCP and AP2 requests/responses."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Capture request body
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            if body:
                try:
                    request_body = json.loads(body.decode())
                except:
                    request_body = body.decode()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Try to get response body from request.state (set by endpoints)
        response_body = getattr(request.state, "response_data", None)

        # Log UCP and AP2 requests
        path = request.url.path
        if path.startswith("/.well-known/ucp") or path.startswith("/ucp/"):
            # Log UCP request
            await self._log_ucp_request(
                request=request,
                response=response,
                request_body=request_body,
                response_body=response_body,
                duration_ms=duration_ms
            )
        elif path.startswith("/ap2/"):
            # Log AP2 request
            await self._log_ap2_request(
                request=request,
                response=response,
                request_body=request_body,
                response_body=response_body,
                duration_ms=duration_ms
            )

        return response

    async def _log_ucp_request(self, request: Request, response: Response, request_body, response_body, duration_ms):
        """Log UCP API request."""
        try:
            async for session in db_manager.get_session():
                log_entry = UCPRequestLog(
                    id=str(uuid.uuid4()),
                    endpoint=request.url.path,
                    method=request.method,
                    query_params=json.dumps(dict(request.query_params)) if request.query_params else None,
                    request_body=json.dumps(request_body) if request_body else None,
                    response_status=response.status_code,
                    response_body=json.dumps(response_body) if response_body else None,
                    client_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    duration_ms=duration_ms
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            print(f"Error logging UCP request: {e}")

    async def _log_ap2_request(self, request: Request, response: Response, request_body, response_body, duration_ms):
        """Log AP2 payment request."""
        try:
            # Extract AP2-specific fields from request
            mandate_id = None
            request_signature = None
            message_type = "unknown"

            if isinstance(request_body, dict):
                if "payment_mandate_contents" in request_body:
                    message_type = "payment_mandate"
                    mandate_id = request_body.get("payment_mandate_contents", {}).get("payment_mandate_id")
                    request_signature = request_body.get("user_authorization")
                elif "otp_code" in request_body:
                    message_type = "otp_verification"
                    mandate_id = request_body.get("mandate_id")

            # Extract AP2-specific fields from response
            response_signature = None
            payment_status = None
            if isinstance(response_body, dict):
                # Extract merchant signature if present
                response_signature = response_body.get("merchant_signature")
                # Extract payment status
                if response_body.get("payment_status"):
                    payment_status = response_body["payment_status"].get("status")

            async for session in db_manager.get_session():
                log_entry = AP2RequestLog(
                    id=str(uuid.uuid4()),
                    endpoint=request.url.path,
                    method=request.method,
                    message_type=message_type,
                    mandate_id=mandate_id,
                    request_body=json.dumps(request_body) if request_body else "{}",
                    request_signature=request_signature,
                    response_status=response.status_code,
                    response_body=json.dumps(response_body) if response_body else "{}",
                    response_signature=response_signature,
                    payment_status=payment_status,
                    client_ip=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    duration_ms=duration_ms
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            print(f"Error logging AP2 request: {e}")


# Add logging middleware
app.add_middleware(RequestLoggingMiddleware)


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
async def get_ucp_profile(request: Request):
    """
    UCP Discovery Endpoint
    Returns merchant capabilities and service endpoints
    """
    merchant_url = os.getenv("MERCHANT_URL", "http://localhost:8451")

    response_data = {
        "ucp": {
            "version": "2026-01-11",
            "services": {
                "dev.ucp.shopping": {
                    "version": "2026-01-11",
                    "spec": "https://ucp.dev/specification/overview",
                    "rest": {
                        "schema": "https://ucp.dev/services/shopping/rest.openapi.json",
                        "endpoint": f"{merchant_url}/ucp/v1"
                    }
                }
            },
            "capabilities": [
                {
                    "name": "dev.ucp.shopping.product_search",
                    "version": "2026-01-11",
                    "spec": "https://ucp.dev/specification/shopping/product_search",
                    "schema": "https://ucp.dev/schemas/shopping/product_search.json"
                },
                {
                    "name": "dev.ucp.shopping.checkout",
                    "version": "2026-01-11",
                    "spec": "https://ucp.dev/specification/checkout",
                    "schema": "https://ucp.dev/schemas/shopping/checkout.json",
                    "extensions": {
                        "ap2_mandate": {
                            "version": "2026-01-11",
                            "spec": "https://ucp.dev/specification/extensions/ap2_mandate",
                            "schema": "https://ucp.dev/schemas/extensions/ap2_mandate.json"
                        },
                        "discount": {
                            "version": "2026-01-11",
                            "spec": "https://ucp.dev/specification/discount",
                            "schema": "https://ucp.dev/schemas/shopping/discount.json",
                            "supported": True,
                            "supports_promocodes": True
                        }
                    }
                }
            ]
        },
        "payment": {
            "ap2_payment": {
                "supported_formats": ["sd-jwt"],
                "mandates_supported": True,
                "otp_verification_supported": True
            }
        },
        "merchant": {
            "id": os.getenv("MERCHANT_ID", "merchant-001"),
            "name": os.getenv("MERCHANT_NAME", "Enhanced Business Store"),
            "url": merchant_url
        }
    }

    # Store response in request.state for logging middleware
    request.state.response_data = response_data

    return response_data


# ============================================================================
# UCP Product Search Endpoint
# ============================================================================

@app.get("/ucp/products/search", response_model=UCPSearchResponse)
async def ucp_search_products(
    request: Request,
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

    response_obj = UCPSearchResponse(
        items=items,
        total=len(items)
    )

    # Store response in request.state for logging middleware
    request.state.response_data = response_obj.dict()

    return response_obj


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
# Merchant Portal - Promocode Management Endpoints
# ============================================================================

class PromocodeCreate(BaseModel):
    """Model for creating a new promocode."""
    code: str
    description: Optional[str] = None
    discount_type: str  # "percentage" or "fixed_amount"
    discount_value: float
    currency: str = "SGD"
    min_purchase_amount: Optional[float] = None
    max_discount_amount: Optional[float] = None
    usage_limit: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class PromocodeUpdate(BaseModel):
    """Model for updating a promocode."""
    description: Optional[str] = None
    discount_value: Optional[float] = None
    min_purchase_amount: Optional[float] = None
    max_discount_amount: Optional[float] = None
    usage_limit: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None


class PromocodeResponse(BaseModel):
    """Promocode response model."""
    id: str
    code: str
    description: Optional[str]
    discount_type: str
    discount_value: float
    currency: str
    min_purchase_amount: Optional[float]
    max_discount_amount: Optional[float]
    usage_limit: Optional[int]
    usage_count: int
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime


@app.get("/api/promocodes", response_model=List[PromocodeResponse])
async def list_promocodes(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    session: AsyncSession = Depends(get_db)
):
    """
    List all promocodes.
    Merchant portal endpoint for viewing promocodes.
    """
    query = select(Promocode)
    if active_only:
        query = query.where(Promocode.is_active == True)

    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    promocodes = result.scalars().all()

    return [
        PromocodeResponse(
            id=p.id,
            code=p.code,
            description=p.description,
            discount_type=p.discount_type,
            discount_value=p.discount_value,
            currency=p.currency,
            min_purchase_amount=p.min_purchase_amount,
            max_discount_amount=p.max_discount_amount,
            usage_limit=p.usage_limit,
            usage_count=p.usage_count,
            valid_from=p.valid_from,
            valid_until=p.valid_until,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in promocodes
    ]


@app.get("/api/promocodes/{promocode_id}", response_model=PromocodeResponse)
async def get_promocode(
    promocode_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get a specific promocode by ID."""
    result = await session.execute(
        select(Promocode).where(Promocode.id == promocode_id)
    )
    promocode = result.scalar_one_or_none()

    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    return PromocodeResponse(
        id=promocode.id,
        code=promocode.code,
        description=promocode.description,
        discount_type=promocode.discount_type,
        discount_value=promocode.discount_value,
        currency=promocode.currency,
        min_purchase_amount=promocode.min_purchase_amount,
        max_discount_amount=promocode.max_discount_amount,
        usage_limit=promocode.usage_limit,
        usage_count=promocode.usage_count,
        valid_from=promocode.valid_from,
        valid_until=promocode.valid_until,
        is_active=promocode.is_active,
        created_at=promocode.created_at,
        updated_at=promocode.updated_at
    )


@app.post("/api/promocodes", response_model=PromocodeResponse, status_code=201)
async def create_promocode(
    promocode: PromocodeCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new promocode.
    Merchant portal endpoint.
    """
    # Validate discount type
    if promocode.discount_type not in ["percentage", "fixed_amount"]:
        raise HTTPException(status_code=400, detail="discount_type must be 'percentage' or 'fixed_amount'")

    # Check if code already exists
    result = await session.execute(
        select(Promocode).where(Promocode.code == promocode.code.upper())
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Promocode already exists")

    # Generate promocode ID
    promocode_id = f"PROMO-{uuid.uuid4().hex[:8].upper()}"

    db_promocode = Promocode(
        id=promocode_id,
        code=promocode.code.upper(),  # Store codes in uppercase
        description=promocode.description,
        discount_type=promocode.discount_type,
        discount_value=promocode.discount_value,
        currency=promocode.currency,
        min_purchase_amount=promocode.min_purchase_amount,
        max_discount_amount=promocode.max_discount_amount,
        usage_limit=promocode.usage_limit,
        valid_from=promocode.valid_from,
        valid_until=promocode.valid_until
    )

    session.add(db_promocode)
    await session.commit()
    await session.refresh(db_promocode)

    return PromocodeResponse(
        id=db_promocode.id,
        code=db_promocode.code,
        description=db_promocode.description,
        discount_type=db_promocode.discount_type,
        discount_value=db_promocode.discount_value,
        currency=db_promocode.currency,
        min_purchase_amount=db_promocode.min_purchase_amount,
        max_discount_amount=db_promocode.max_discount_amount,
        usage_limit=db_promocode.usage_limit,
        usage_count=db_promocode.usage_count,
        valid_from=db_promocode.valid_from,
        valid_until=db_promocode.valid_until,
        is_active=db_promocode.is_active,
        created_at=db_promocode.created_at,
        updated_at=db_promocode.updated_at
    )


@app.put("/api/promocodes/{promocode_id}", response_model=PromocodeResponse)
async def update_promocode(
    promocode_id: str,
    promocode_update: PromocodeUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    Update an existing promocode.
    Merchant portal endpoint.
    """
    result = await session.execute(
        select(Promocode).where(Promocode.id == promocode_id)
    )
    db_promocode = result.scalar_one_or_none()

    if not db_promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    # Update fields
    update_data = promocode_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_promocode, field, value)

    db_promocode.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(db_promocode)

    return PromocodeResponse(
        id=db_promocode.id,
        code=db_promocode.code,
        description=db_promocode.description,
        discount_type=db_promocode.discount_type,
        discount_value=db_promocode.discount_value,
        currency=db_promocode.currency,
        min_purchase_amount=db_promocode.min_purchase_amount,
        max_discount_amount=db_promocode.max_discount_amount,
        usage_limit=db_promocode.usage_limit,
        usage_count=db_promocode.usage_count,
        valid_from=db_promocode.valid_from,
        valid_until=db_promocode.valid_until,
        is_active=db_promocode.is_active,
        created_at=db_promocode.created_at,
        updated_at=db_promocode.updated_at
    )


@app.delete("/api/promocodes/{promocode_id}")
async def delete_promocode(
    promocode_id: str,
    hard_delete: bool = False,
    session: AsyncSession = Depends(get_db)
):
    """
    Delete a promocode (soft delete by default).
    Merchant portal endpoint.
    """
    result = await session.execute(
        select(Promocode).where(Promocode.id == promocode_id)
    )
    db_promocode = result.scalar_one_or_none()

    if not db_promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    if hard_delete:
        await session.delete(db_promocode)
    else:
        db_promocode.is_active = False
        db_promocode.updated_at = datetime.utcnow()

    await session.commit()

    return {"message": "Promocode deleted successfully", "promocode_id": promocode_id}


# ============================================================================
# UCP Checkout Endpoints (wrapping AP2 Payment)
# ============================================================================

class LineItem(BaseModel):
    """UCP line item."""
    id: str
    sku: str
    name: str
    quantity: int
    price: float

class CheckoutSessionCreate(BaseModel):
    """Create checkout session request."""
    line_items: List[LineItem]
    buyer_email: str
    currency: str = "SGD"
    promocode: Optional[str] = None  # Optional promocode to apply

class CheckoutSessionUpdate(BaseModel):
    """Update checkout session request."""
    payment_mandate: Optional[Dict[str, Any]] = None
    user_signature: Optional[str] = None
    promocode: Optional[str] = None  # Optional promocode to apply/update

class CheckoutSessionResponse(BaseModel):
    """Checkout session response."""
    id: str
    status: str  # incomplete, ready_for_complete, complete, cancelled
    line_items: List[LineItem]
    totals: Dict[str, Any]
    payment: Optional[Dict[str, Any]] = None
    ap2: Optional[Dict[str, Any]] = None

# In-memory checkout sessions (in production, use database)
checkout_sessions: Dict[str, Dict[str, Any]] = {}

@app.post("/ucp/v1/checkout-sessions", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: Request,
    checkout: CheckoutSessionCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    UCP: Create checkout session.
    Returns checkout session with status 'incomplete'.
    Supports optional promocode for discounts.
    """
    session_id = f"cs_{uuid.uuid4().hex[:16]}"

    # Calculate subtotal
    subtotal = sum(item.price * item.quantity for item in checkout.line_items)

    # Initialize totals
    discount = 0.0
    promocode_applied = None
    promocode_error = None

    # Apply promocode if provided
    if checkout.promocode:
        code_upper = checkout.promocode.upper()
        result = await session.execute(
            select(Promocode).where(Promocode.code == code_upper)
        )
        promo = result.scalar_one_or_none()

        if promo:
            is_valid, error_msg = promo.is_valid(purchase_amount=subtotal)
            if is_valid:
                discount = promo.calculate_discount(subtotal)
                promocode_applied = {
                    "code": promo.code,
                    "description": promo.description,
                    "discount_type": promo.discount_type,
                    "discount_value": promo.discount_value,
                    "discount_amount": discount
                }
            else:
                promocode_error = error_msg
        else:
            promocode_error = "Invalid promocode"

    total = max(0, subtotal - discount)

    checkout_data = {
        "id": session_id,
        "status": "incomplete",
        "line_items": [item.dict() for item in checkout.line_items],
        "buyer_email": checkout.buyer_email,
        "totals": {
            "subtotal": subtotal,
            "discount": discount,
            "tax": 0.0,
            "total": total,
            "currency": checkout.currency
        },
        "created_at": datetime.utcnow().isoformat()
    }

    if promocode_applied:
        checkout_data["promocode"] = promocode_applied
    if promocode_error:
        checkout_data["promocode_error"] = promocode_error

    checkout_sessions[session_id] = checkout_data

    response_data = CheckoutSessionResponse(**checkout_data)
    request.state.response_data = response_data.dict()

    return response_data

@app.get("/ucp/v1/checkout-sessions/{session_id}", response_model=CheckoutSessionResponse)
async def get_checkout_session(
    request: Request,
    session_id: str
):
    """UCP: Get checkout session by ID."""
    if session_id not in checkout_sessions:
        raise HTTPException(status_code=404, detail="Checkout session not found")

    checkout_data = checkout_sessions[session_id]
    response_data = CheckoutSessionResponse(**checkout_data)
    request.state.response_data = response_data.dict()

    return response_data

@app.put("/ucp/v1/checkout-sessions/{session_id}", response_model=CheckoutSessionResponse)
async def update_checkout_session(
    request: Request,
    session_id: str,
    update: CheckoutSessionUpdate,
    session: AsyncSession = Depends(get_db)
):
    """
    UCP: Update checkout session with payment mandate or promocode.
    Transitions status to 'ready_for_complete' when payment mandate is provided.
    """
    if session_id not in checkout_sessions:
        raise HTTPException(status_code=404, detail="Checkout session not found")

    checkout_data = checkout_sessions[session_id]

    # Update promocode if provided
    if update.promocode:
        code_upper = update.promocode.upper()
        result = await session.execute(
            select(Promocode).where(Promocode.code == code_upper)
        )
        promo = result.scalar_one_or_none()

        # Recalculate totals
        subtotal = checkout_data["totals"]["subtotal"]
        discount = 0.0
        promocode_applied = None
        promocode_error = None

        if promo:
            is_valid, error_msg = promo.is_valid(purchase_amount=subtotal)
            if is_valid:
                discount = promo.calculate_discount(subtotal)
                promocode_applied = {
                    "code": promo.code,
                    "description": promo.description,
                    "discount_type": promo.discount_type,
                    "discount_value": promo.discount_value,
                    "discount_amount": discount
                }
            else:
                promocode_error = error_msg
        else:
            promocode_error = "Invalid promocode"

        total = max(0, subtotal - discount)

        checkout_data["totals"]["discount"] = discount
        checkout_data["totals"]["total"] = total

        if promocode_applied:
            checkout_data["promocode"] = promocode_applied
            # Remove error if it was previously set
            checkout_data.pop("promocode_error", None)
        if promocode_error:
            checkout_data["promocode_error"] = promocode_error
            # Remove promocode if it was previously set
            checkout_data.pop("promocode", None)

    # Update with payment mandate if provided
    if update.payment_mandate:
        checkout_data["payment_mandate"] = update.payment_mandate
        checkout_data["user_signature"] = update.user_signature
        checkout_data["status"] = "ready_for_complete"
        checkout_data["ap2"] = {
            "mandate_id": update.payment_mandate.get("payment_mandate_contents", {}).get("payment_mandate_id"),
            "user_authorization": update.user_signature
        }

    checkout_sessions[session_id] = checkout_data

    response_data = CheckoutSessionResponse(**checkout_data)
    request.state.response_data = response_data.dict()

    return response_data

@app.post("/ucp/v1/checkout-sessions/{session_id}/complete")
async def complete_checkout_session(
    request: Request,
    session_id: str,
    otp_code: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """
    UCP: Complete checkout session.
    Processes AP2 payment mandate and returns final receipt.
    Increments promocode usage count if payment is successful.
    """
    if session_id not in checkout_sessions:
        raise HTTPException(status_code=404, detail="Checkout session not found")

    checkout_data = checkout_sessions[session_id]

    if checkout_data["status"] != "ready_for_complete":
        raise HTTPException(status_code=400, detail="Checkout session not ready for completion")

    # Get payment mandate from checkout session
    payment_mandate = checkout_data.get("payment_mandate")
    if not payment_mandate:
        raise HTTPException(status_code=400, detail="Payment mandate missing")

    # Process through AP2 payment agent
    payment_agent = app.state.payment_agent
    mandate_obj = AP2PaymentMandate(**payment_mandate)

    # If OTP code provided, verify it
    if otp_code:
        otp_verification = OTPVerification(
            payment_mandate_id=mandate_obj.payment_mandate_contents.payment_mandate_id,
            otp_code=otp_code
        )

        if not payment_agent.verify_otp(
            otp_verification.payment_mandate_id,
            otp_verification.otp_code
        ):
            raise HTTPException(status_code=400, detail="Invalid OTP code")

        receipt = payment_agent.process_payment(mandate_obj)
    else:
        # Check if OTP challenge needed
        if payment_agent.should_raise_otp_challenge(mandate_obj):
            challenge = payment_agent.create_otp_challenge(mandate_obj)
            checkout_data["status"] = "requires_escalation"
            checkout_data["otp_challenge"] = challenge.dict()

            response_data = {
                "status": "otp_required",
                "checkout": checkout_data,
                "otp_challenge": challenge.dict()
            }
            request.state.response_data = response_data
            return response_data

        # Process payment
        receipt = payment_agent.process_payment(mandate_obj)

    # If payment successful and promocode was applied, increment usage count
    if isinstance(receipt.payment_status, PaymentReceiptSuccess) and "promocode" in checkout_data:
        promocode_code = checkout_data["promocode"]["code"]
        result = await session.execute(
            select(Promocode).where(Promocode.code == promocode_code)
        )
        promo = result.scalar_one_or_none()
        if promo:
            promo.usage_count += 1
            await session.commit()

    # Update checkout session with completion
    checkout_data["status"] = "complete"
    checkout_data["receipt"] = receipt.dict()
    checkout_data["completed_at"] = datetime.utcnow().isoformat()

    response_data = {
        "status": "success",
        "checkout": checkout_data,
        "receipt": receipt.dict()
    }
    request.state.response_data = response_data

    return response_data


# Helper function for payment agent
def get_payment_agent() -> MerchantPaymentAgent:
    """Get payment agent instance."""
    return app.state.payment_agent


# ============================================================================
# Settings API Endpoints
# ============================================================================

class MerchantSettings(BaseModel):
    """Merchant settings response."""
    merchant_name: str
    merchant_id: str
    merchant_url: str
    otp_enabled: bool
    otp_amount_threshold: float


class MerchantSettingsUpdate(BaseModel):
    """Merchant settings update request."""
    otp_enabled: Optional[bool] = None
    otp_amount_threshold: Optional[float] = None


@app.get("/api/settings", response_model=MerchantSettings)
async def get_settings():
    """Get current merchant settings."""
    payment_agent = app.state.payment_agent

    return MerchantSettings(
        merchant_name=os.getenv("MERCHANT_NAME", "Enhanced Business Store"),
        merchant_id=os.getenv("MERCHANT_ID", "merchant-001"),
        merchant_url=os.getenv("MERCHANT_URL", "http://localhost:8453"),
        otp_enabled=payment_agent.otp_enabled,
        otp_amount_threshold=payment_agent.otp_amount_threshold
    )


@app.put("/api/settings")
async def update_settings(settings: MerchantSettingsUpdate):
    """
    Update merchant settings.
    Note: These changes are in-memory only and will reset on restart.
    For persistent changes, update the .env file.
    """
    payment_agent = app.state.payment_agent

    if settings.otp_enabled is not None:
        payment_agent.otp_enabled = settings.otp_enabled
        logger.info(f"OTP enabled setting updated to: {settings.otp_enabled}")

    if settings.otp_amount_threshold is not None:
        payment_agent.otp_amount_threshold = settings.otp_amount_threshold
        logger.info(f"OTP amount threshold updated to: ${settings.otp_amount_threshold}")

    return {
        "message": "Settings updated successfully (in-memory only)",
        "otp_enabled": payment_agent.otp_enabled,
        "otp_amount_threshold": payment_agent.otp_amount_threshold
    }


# ============================================================================
# Dashboard API Endpoints
# ============================================================================

@app.get("/api/dashboard/ucp-logs")
async def get_ucp_logs(
    limit: int = 50,
    offset: int = 0,
    endpoint_filter: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """Get UCP request logs for dashboard."""
    query = select(UCPRequestLog).order_by(desc(UCPRequestLog.created_at))

    if endpoint_filter:
        query = query.where(UCPRequestLog.endpoint.like(f"%{endpoint_filter}%"))

    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    logs = result.scalars().all()

    return {
        "logs": [log.to_dict() for log in logs],
        "total": len(logs),
        "limit": limit,
        "offset": offset
    }


@app.get("/api/dashboard/ap2-logs")
async def get_ap2_logs(
    limit: int = 50,
    offset: int = 0,
    message_type_filter: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """Get AP2 payment request logs for dashboard."""
    query = select(AP2RequestLog).order_by(desc(AP2RequestLog.created_at))

    if message_type_filter:
        query = query.where(AP2RequestLog.message_type == message_type_filter)

    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    logs = result.scalars().all()

    return {
        "logs": [log.to_dict() for log in logs],
        "total": len(logs),
        "limit": limit,
        "offset": offset
    }


@app.get("/api/dashboard/stats")
async def get_dashboard_stats(session: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    # Count UCP requests
    ucp_count_result = await session.execute(select(UCPRequestLog))
    ucp_count = len(ucp_count_result.scalars().all())

    # Count AP2 requests
    ap2_count_result = await session.execute(select(AP2RequestLog))
    ap2_count = len(ap2_count_result.scalars().all())

    # Count successful payments
    ap2_success_result = await session.execute(
        select(AP2RequestLog).where(AP2RequestLog.payment_status == "success")
    )
    payment_success_count = len(ap2_success_result.scalars().all())

    return {
        "total_ucp_requests": ucp_count,
        "total_ap2_requests": ap2_count,
        "successful_payments": payment_success_count,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.delete("/api/dashboard/clear-logs")
async def clear_all_logs(session: AsyncSession = Depends(get_db)):
    """Clear all UCP and AP2 logs from the dashboard."""
    try:
        # Delete all UCP logs
        await session.execute(UCPRequestLog.__table__.delete())

        # Delete all AP2 logs
        await session.execute(AP2RequestLog.__table__.delete())

        await session.commit()

        return {
            "status": "success",
            "message": "All logs cleared successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear logs: {str(e)}")


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
