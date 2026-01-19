"""Database configuration and models for chat backend - User credentials storage."""

from sqlalchemy import Column, String, Float, Integer, Text, DateTime, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import json
import os

Base = declarative_base()


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

    # Mastercard Tokenization fields
    mastercard_token = Column(String)  # Network token from Mastercard
    mastercard_token_ref = Column(String)  # Token unique reference
    mastercard_token_assurance = Column(String)  # Token assurance level
    tokenization_date = Column(DateTime)  # When card was tokenized
    is_tokenized = Column(Boolean, default=False)  # Whether card is tokenized

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
    checkout_session_id = Column(String)  # UCP checkout session ID
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


class MastercardAuthenticationChallenge(Base):
    """Track Mastercard authentication challenges during payment."""
    __tablename__ = "mastercard_auth_challenges"

    id = Column(String, primary_key=True)
    payment_mandate_id = Column(String, ForeignKey("payment_mandates.id"), nullable=False)
    challenge_id = Column(String, nullable=False)  # Mastercard challenge ID
    transaction_id = Column(String, nullable=False)  # Transaction identifier
    authentication_method = Column(String)  # "otp", "biometric", "none"
    status = Column(String, default="pending")  # "pending", "approved", "declined", "expired"
    verification_code = Column(String)  # Store OTP temporarily (hashed in production)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime)
    expires_at = Column(DateTime)
    raw_response = Column(Text)  # JSON response from Mastercard API

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "payment_mandate_id": self.payment_mandate_id,
            "challenge_id": self.challenge_id,
            "authentication_method": self.authentication_method,
            "status": self.status,
            "attempts": self.attempts,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None
        }


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, database_url: str = "sqlite+aiosqlite:///./chat_app.db"):
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
database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./chat_app.db")
db_manager = DatabaseManager(database_url)
