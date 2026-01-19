"""
AP2 (Agentic Payment Protocol) Types
Simplified implementation for payment mandate and receipt handling.
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class PaymentCurrencyAmount(BaseModel):
    """Payment amount with currency."""
    currency: str = "SGD"
    value: float


class PaymentItem(BaseModel):
    """Individual payment item."""
    label: str
    amount: PaymentCurrencyAmount
    pending: Optional[bool] = None


class PaymentDetails(BaseModel):
    """Payment details from mandate."""
    id: str
    total: PaymentItem
    display_items: Optional[List[PaymentItem]] = None


class PaymentResponse(BaseModel):
    """Payment response from consumer."""
    request_id: str
    method_name: str  # "CARD"
    details: Optional[Dict[str, Any]] = None
    payer_email: Optional[str] = None
    payer_name: Optional[str] = None


class PaymentMandateContents(BaseModel):
    """Contents of a payment mandate."""
    payment_mandate_id: str
    timestamp: str
    payment_details_id: str
    payment_details_total: PaymentItem
    payment_response: PaymentResponse
    merchant_agent: str


class PaymentMandate(BaseModel):
    """
    AP2 Payment Mandate - signed payment instructions from consumer.
    This is sent from chat backend (consumer) to merchant backend.
    """
    payment_mandate_contents: PaymentMandateContents
    user_authorization: Optional[str] = None  # Passkey signature


class PaymentReceiptSuccess(BaseModel):
    """Successful payment status."""
    merchant_confirmation_id: str
    psp_confirmation_id: Optional[str] = None
    network_confirmation_id: Optional[str] = None


class PaymentReceiptError(BaseModel):
    """Error payment status."""
    error_message: str


class PaymentReceiptFailure(BaseModel):
    """Failed payment status."""
    failure_message: str


class PaymentReceipt(BaseModel):
    """
    AP2 Payment Receipt - confirmation of payment processing.
    This is returned from merchant backend to chat backend.
    """
    payment_mandate_id: str
    timestamp: str
    payment_id: str
    amount: PaymentCurrencyAmount
    payment_status: PaymentReceiptSuccess | PaymentReceiptError | PaymentReceiptFailure
    payment_method_details: Optional[Dict[str, Any]] = None


class OTPChallenge(BaseModel):
    """OTP challenge for payment verification."""
    payment_mandate_id: str
    message: str
    otp_sent_to: Optional[str] = None


class OTPVerification(BaseModel):
    """OTP verification from user."""
    payment_mandate_id: str
    otp_code: str
