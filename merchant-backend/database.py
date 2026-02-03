"""Database configuration and models using SQLAlchemy."""

from sqlalchemy import Column, String, Float, Integer, Text, DateTime, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json
import os

Base = declarative_base()


class Product(Base):
    """Product model for persistent storage."""
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    sku = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    currency = Column(String, default="SGD")
    category = Column(String)
    brand = Column(String)
    image_url = Column(Text)  # JSON array of image URLs
    availability = Column(String, default="https://schema.org/InStock")
    condition = Column(String, default="https://schema.org/NewCondition")
    gtin = Column(String)
    mpn = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def to_schema_org(self):
        """Convert to Schema.org Product format compatible with business_agent."""
        return {
            "@type": "Product",
            "productID": self.id,
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "image": json.loads(self.image_url) if self.image_url else [],
            "brand": {"@type": "Brand", "name": self.brand} if self.brand else None,
            "offers": {
                "@type": "Offer",
                "price": str(self.price),
                "priceCurrency": self.currency,
                "availability": self.availability,
                "itemCondition": self.condition
            },
            "category": self.category,
            "gtin": self.gtin,
            "mpn": self.mpn
        }


class User(Base):
    """User model for authentication and payment."""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String)
    passkey_credential_id = Column(String, unique=True)  # WebAuthn credential ID
    passkey_public_key = Column(Text)  # WebAuthn public key (PEM or JWK format)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    payment_cards = relationship("PaymentCard", back_populates="user")
    payment_mandates = relationship("PaymentMandate", back_populates="user")


class PaymentCard(Base):
    """Payment card model for storing user payment methods."""
    __tablename__ = "payment_cards"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    user_email = Column(String, nullable=False, index=True)
    card_number_encrypted = Column(String, nullable=False)  # Encrypted card number
    card_last_four = Column(String, nullable=False)  # Last 4 digits for display
    card_network = Column(String, nullable=False)  # "mastercard", "visa", etc.
    card_holder_name = Column(String)
    expiry_month = Column(Integer)
    expiry_year = Column(Integer)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="payment_cards")
    payment_mandates = relationship("PaymentMandate", back_populates="payment_card")

    def to_dict(self, masked=True):
        """Convert to dictionary, optionally masking sensitive data."""
        if masked:
            return {
                "id": self.id,
                "user_email": self.user_email,
                "card_last_four": self.card_last_four,
                "card_network": self.card_network,
                "card_holder_name": self.card_holder_name,
                "is_default": self.is_default,
                "created_at": self.created_at.isoformat() if self.created_at else None
            }
        else:
            # Only return full data in secure contexts
            return {
                "id": self.id,
                "user_email": self.user_email,
                "card_number_encrypted": self.card_number_encrypted,
                "card_last_four": self.card_last_four,
                "card_network": self.card_network,
                "card_holder_name": self.card_holder_name,
                "expiry_month": self.expiry_month,
                "expiry_year": self.expiry_year,
                "is_default": self.is_default
            }


class PaymentMandate(Base):
    """Payment mandate model for AP2 protocol."""
    __tablename__ = "payment_mandates"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    user_email = Column(String, nullable=False, index=True)
    cart_id = Column(String, nullable=False)
    payment_card_id = Column(String, ForeignKey("payment_cards.id"), nullable=False)
    total_amount = Column(Float, nullable=False)
    currency = Column(String, default="SGD")
    mandate_data = Column(Text)  # JSON: Full AP2 PaymentMandate structure
    user_signature = Column(Text)  # WebAuthn signature
    status = Column(String, default="pending")  # "pending", "signed", "processing", "completed", "failed"
    created_at = Column(DateTime, default=datetime.utcnow)
    signed_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Relationships
    user = relationship("User", back_populates="payment_mandates")
    payment_card = relationship("PaymentCard", back_populates="payment_mandates")
    receipt = relationship("PaymentReceipt", back_populates="payment_mandate", uselist=False)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_email": self.user_email,
            "cart_id": self.cart_id,
            "payment_card_id": self.payment_card_id,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "mandate_data": json.loads(self.mandate_data) if self.mandate_data else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class PaymentReceipt(Base):
    """Payment receipt model for completed transactions."""
    __tablename__ = "payment_receipts"

    id = Column(String, primary_key=True)
    payment_mandate_id = Column(String, ForeignKey("payment_mandates.id"), nullable=False, unique=True)
    confirmation_id = Column(String, unique=True, nullable=False)  # Merchant confirmation
    psp_confirmation_id = Column(String)  # Payment service provider confirmation
    network_confirmation_id = Column(String)  # Card network confirmation
    amount = Column(Float, nullable=False)
    currency = Column(String, default="SGD")
    status = Column(String, nullable=False)  # "success", "error", "failure"
    receipt_data = Column(Text)  # JSON: Full AP2 PaymentReceipt structure
    error_message = Column(Text)  # Error details if status is "error" or "failure"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    payment_mandate = relationship("PaymentMandate", back_populates="receipt")

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "payment_mandate_id": self.payment_mandate_id,
            "confirmation_id": self.confirmation_id,
            "psp_confirmation_id": self.psp_confirmation_id,
            "network_confirmation_id": self.network_confirmation_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "receipt_data": json.loads(self.receipt_data) if self.receipt_data else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class UCPRequestLog(Base):
    """Log of UCP API requests and responses."""
    __tablename__ = "ucp_request_logs"

    id = Column(String, primary_key=True)
    endpoint = Column(String, nullable=False, index=True)  # e.g., "/.well-known/ucp", "/ucp/products/search"
    method = Column(String, nullable=False)  # GET, POST, etc.
    query_params = Column(Text)  # JSON: Query parameters
    request_body = Column(Text)  # JSON: Request body if any
    response_status = Column(Integer, nullable=False)  # HTTP status code
    response_body = Column(Text)  # JSON: Response sent
    client_ip = Column(String)
    user_agent = Column(String)
    duration_ms = Column(Float)  # Request duration in milliseconds
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "endpoint": self.endpoint,
            "method": self.method,
            "query_params": json.loads(self.query_params) if self.query_params else {},
            "request_body": json.loads(self.request_body) if self.request_body else None,
            "response_status": self.response_status,
            "response_body": json.loads(self.response_body) if self.response_body else None,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class AP2RequestLog(Base):
    """Log of AP2 payment protocol messages."""
    __tablename__ = "ap2_request_logs"

    id = Column(String, primary_key=True)
    endpoint = Column(String, nullable=False, index=True)  # e.g., "/ap2/payment/process"
    method = Column(String, nullable=False)  # POST
    message_type = Column(String, nullable=False, index=True)  # "payment_mandate", "otp_verification", "payment_receipt"
    mandate_id = Column(String, index=True)  # Payment mandate ID for correlation
    request_body = Column(Text, nullable=False)  # JSON: Full AP2 message including signature
    request_signature = Column(Text)  # User signature from AP2 message
    response_status = Column(Integer, nullable=False)  # HTTP status code
    response_body = Column(Text, nullable=False)  # JSON: AP2 response message
    response_signature = Column(Text)  # Merchant signature in response
    payment_status = Column(String)  # "success", "otp_required", "failed"
    client_ip = Column(String)
    user_agent = Column(String)
    duration_ms = Column(Float)  # Request duration in milliseconds
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "endpoint": self.endpoint,
            "method": self.method,
            "message_type": self.message_type,
            "mandate_id": self.mandate_id,
            "request_body": json.loads(self.request_body) if self.request_body else None,
            "request_signature": self.request_signature,
            "response_status": self.response_status,
            "response_body": json.loads(self.response_body) if self.response_body else None,
            "response_signature": self.response_signature,
            "payment_status": self.payment_status,
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Promocode(Base):
    """Promocode/Voucher model for merchant discounts."""
    __tablename__ = "promocodes"

    id = Column(String, primary_key=True)
    code = Column(String, unique=True, nullable=False, index=True)  # Promocode (e.g., "SAVE10")
    description = Column(Text)  # Description of the promocode
    discount_type = Column(String, nullable=False)  # "percentage" or "fixed_amount"
    discount_value = Column(Float, nullable=False)  # 10 for 10% or 5.00 for $5
    currency = Column(String, default="SGD")  # For fixed_amount discounts
    min_purchase_amount = Column(Float)  # Minimum purchase amount required
    max_discount_amount = Column(Float)  # Maximum discount cap for percentage discounts
    usage_limit = Column(Integer)  # Maximum number of times this code can be used (null = unlimited)
    usage_count = Column(Integer, default=0)  # Number of times this code has been used
    valid_from = Column(DateTime)  # Start date (null = valid from creation)
    valid_until = Column(DateTime)  # Expiration date (null = no expiration)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_valid(self, purchase_amount: float = None) -> tuple[bool, str]:
        """
        Check if promocode is valid.

        Returns:
            (is_valid, error_message)
        """
        now = datetime.utcnow()

        # Check if active
        if not self.is_active:
            return False, "Promocode is not active"

        # Check usage limit
        if self.usage_limit is not None and self.usage_count >= self.usage_limit:
            return False, "Promocode has reached its usage limit"

        # Check valid_from date
        if self.valid_from and now < self.valid_from:
            return False, "Promocode is not yet valid"

        # Check valid_until date
        if self.valid_until and now > self.valid_until:
            return False, "Promocode has expired"

        # Check minimum purchase amount
        if purchase_amount is not None and self.min_purchase_amount is not None:
            if purchase_amount < self.min_purchase_amount:
                return False, f"Minimum purchase amount of {self.currency} {self.min_purchase_amount} required"

        return True, ""

    def calculate_discount(self, purchase_amount: float) -> float:
        """
        Calculate discount amount for given purchase amount.

        Args:
            purchase_amount: Total purchase amount before discount

        Returns:
            Discount amount
        """
        if self.discount_type == "percentage":
            discount = purchase_amount * (self.discount_value / 100.0)
            # Apply max discount cap if specified
            if self.max_discount_amount is not None:
                discount = min(discount, self.max_discount_amount)
            return round(discount, 2)
        elif self.discount_type == "fixed_amount":
            # Fixed amount discount cannot exceed purchase amount
            return min(self.discount_value, purchase_amount)
        else:
            return 0.0

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "code": self.code,
            "description": self.description,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "currency": self.currency,
            "min_purchase_amount": self.min_purchase_amount,
            "max_discount_amount": self.max_discount_amount,
            "usage_limit": self.usage_limit,
            "usage_count": self.usage_count,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, database_url: str = "sqlite+aiosqlite:///./enhanced_app.db"):
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None

    def init_db(self):
        """Initialize database connection and create tables."""
        # For SQLite, use synchronous engine for table creation
        sync_url = self.database_url.replace("+aiosqlite", "")
        sync_engine = create_engine(sync_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=sync_engine)

        # Create async session maker
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            future=True
        )
        self.SessionLocal = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def get_session(self):
        """Get database session."""
        async with self.SessionLocal() as session:
            yield session


# Global database manager instance
# Get database URL from environment variable or use default
database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./enhanced_app.db")
db_manager = DatabaseManager(database_url)
