"""
Enhanced Business Agent Application
Combines FastAPI backend with Ollama LLM and merchant portal capabilities.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uvicorn
import json
import os
from datetime import datetime
from dotenv import load_dotenv

from database import db_manager, Product
from ollama_agent import EnhancedBusinessAgent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Load environment variables
load_dotenv()


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


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    # Startup
    db_manager.init_db()

    # Get configuration from environment variables
    ollama_url = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")

    app.state.agent = EnhancedBusinessAgent(
        ollama_url=ollama_url,
        model_name=ollama_model
    )

    # Seed database with sample products if empty
    await seed_initial_products()

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
                    image_url=json.dumps(["https://example.com/cookies.jpg"]),
                ),
                Product(
                    id="PROD-002",
                    sku="STRAW-001",
                    name="Fresh Strawberries",
                    description="Sweet and juicy fresh strawberries",
                    price=4.49,
                    category="Produce/Fruits",
                    brand="FarmFresh",
                    image_url=json.dumps(["https://example.com/strawberries.jpg"]),
                ),
                Product(
                    id="PROD-003",
                    sku="CHIPS-001",
                    name="Classic Potato Chips",
                    description="Crispy salted potato chips",
                    price=3.79,
                    category="Snacks/Chips",
                    brand="CrunchTime",
                    image_url=json.dumps(["https://example.com/chips.jpg"]),
                ),
                Product(
                    id="PROD-004",
                    sku="SW-CHIPS-001",
                    name="Baked Sweet Potato Chips",
                    description="Healthy baked sweet potato chips",
                    price=4.79,
                    category="Snacks/Chips",
                    brand="HealthyChoice",
                    image_url=json.dumps(["https://example.com/sweet-chips.jpg"]),
                ),
                Product(
                    id="PROD-005",
                    sku="O-COOKIES-001",
                    name="Classic Oat Cookies",
                    description="Wholesome oatmeal cookies with raisins",
                    price=5.99,
                    category="Bakery/Cookies",
                    brand="HomeBaked",
                    image_url=json.dumps(["https://example.com/oat-cookies.jpg"]),
                ),
                Product(
                    id="PROD-006",
                    sku="NUTRIBAR-001",
                    name="Nutri-Bar",
                    description="Nutritious energy bar with nuts and fruits",
                    price=2.99,
                    category="Snacks/Bars",
                    brand="EnergyPlus",
                    image_url=json.dumps(["https://example.com/nutribar.jpg"]),
                ),
            ]

            session.add_all(sample_products)
            await session.commit()


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Enhanced Business Agent API",
    description="AI-powered shopping assistant with merchant portal",
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


def get_agent() -> EnhancedBusinessAgent:
    """Get agent instance."""
    return app.state.agent


# ============================================================================
# Chat Endpoints
# ============================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    agent: EnhancedBusinessAgent = Depends(get_agent)
):
    """
    Send a message to the shopping assistant agent.
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
# Merchant Portal - Product Management Endpoints
# ============================================================================

@app.get("/api/merchant/products", response_model=List[ProductResponse])
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


@app.get("/api/merchant/products/{product_id}", response_model=ProductResponse)
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


@app.post("/api/merchant/products", response_model=ProductResponse, status_code=201)
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


@app.put("/api/merchant/products/{product_id}", response_model=ProductResponse)
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


@app.delete("/api/merchant/products/{product_id}")
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
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "enhanced-business-agent",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8452))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
