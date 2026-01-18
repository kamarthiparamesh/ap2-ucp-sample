# Universal Commerce Protocol (UCP) - Implementation Knowledge Base

**Version:** 2026-01-11
**Specification:** https://ucp.dev/specification/
**Last Updated:** 2026-01-18

This document captures the complete implementation knowledge of the Universal Commerce Protocol (UCP) with Agent Payments Protocol (AP2) integration, based on production implementation experience.

---

## Table of Contents

1. [UCP Overview](#ucp-overview)
2. [Discovery Endpoint](#discovery-endpoint)
3. [UCP Checkout Sessions](#ucp-checkout-sessions)
4. [AP2 Integration with UCP](#ap2-integration-with-ucp)
5. [Implementation Patterns](#implementation-patterns)
6. [Database Schema](#database-schema)
7. [Request/Response Logging](#requestresponse-logging)
8. [Common Pitfalls & Solutions](#common-pitfalls--solutions)
9. [Testing & Debugging](#testing--debugging)
10. [Production Considerations](#production-considerations)

---

## UCP Overview

### What is UCP?

Universal Commerce Protocol (UCP) is a standardized protocol for commerce interactions between independent systems. It enables:

- **Service Discovery**: Systems advertise capabilities via `/.well-known/ucp`
- **Product Search**: Standardized product discovery endpoints
- **Checkout Sessions**: Stateful checkout flows with payment integration
- **Protocol Compatibility**: Works with AP2, A2A, and MCP protocols

### Key Principles

1. **Date-based versioning**: `YYYY-MM-DD` format (e.g., "2026-01-11")
2. **Declarative capabilities**: Systems advertise what they support
3. **Extension system**: Capabilities can have extensions (e.g., AP2 mandates)
4. **RESTful design**: Standard HTTP methods and JSON payloads
5. **Price format**: Prices in cents/smallest currency unit (UCP standard)

### Architecture Pattern

```
┌─────────────────────┐
│   UCP Client        │  (Consumer System)
│   - Discovers       │
│   - Requests        │
│   - Consumes        │
└──────────┬──────────┘
           │
           │ HTTPS/JSON
           │
┌──────────▼──────────┐
│   UCP Server        │  (Provider System)
│   - Advertises      │
│   - Serves          │
│   - Processes       │
└─────────────────────┘
```

---

## Discovery Endpoint

### Endpoint Structure

**Path:** `/.well-known/ucp`
**Method:** `GET`
**Content-Type:** `application/json`

### Complete Discovery Response

```json
{
  "ucp": {
    "version": "2026-01-11",
    "services": {
      "dev.ucp.shopping": {
        "version": "2026-01-11",
        "spec": "https://ucp.dev/specification/overview",
        "rest": {
          "schema": "https://ucp.dev/services/shopping/rest.openapi.json",
          "endpoint": "http://localhost:8453/ucp/v1"
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
          }
        }
      }
    ]
  },
  "payment": {
    "ap2_payment": {
      "supported_formats": ["sd-jwt"],
      "mandates_supported": true,
      "otp_verification_supported": true
    }
  },
  "merchant": {
    "id": "merchant-001",
    "name": "Enhanced Business Store",
    "url": "http://localhost:8453"
  }
}
```

### Implementation (FastAPI)

```python
from fastapi import FastAPI, Request
from typing import Dict, Any
import os

app = FastAPI()

@app.get("/.well-known/ucp")
async def get_ucp_profile(request: Request):
    """
    UCP Discovery Endpoint
    Returns merchant capabilities and service endpoints
    """
    merchant_url = os.getenv("MERCHANT_URL", "http://localhost:8453")

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

    # Optional: Store for logging
    request.state.response_data = response_data

    return response_data
```

### Key Points

- ✅ **Endpoint must be at root** `/.well-known/ucp` (not `/api/.well-known/ucp`)
- ✅ **Service endpoint** should point to base path (e.g., `/ucp/v1`)
- ✅ **Version format** is date-based (`YYYY-MM-DD`)
- ✅ **Extensions** are declared within capabilities
- ✅ **Payment section** is separate from UCP section

---

## UCP Checkout Sessions

### Endpoint Structure

UCP checkout follows a stateful session model with 4 main endpoints:

1. **Create Session** - `POST /ucp/v1/checkout-sessions`
2. **Get Session** - `GET /ucp/v1/checkout-sessions/{id}`
3. **Update Session** - `PUT /ucp/v1/checkout-sessions/{id}`
4. **Complete Session** - `POST /ucp/v1/checkout-sessions/{id}/complete`

### Session Status Flow

```
incomplete → ready_for_complete → complete
                ↓
         requires_escalation (OTP needed)
                ↓
            complete
```

### 1. Create Checkout Session

**Endpoint:** `POST /ucp/v1/checkout-sessions`

**Request:**
```json
{
  "line_items": [
    {
      "id": "PROD-001",
      "sku": "PROD-001",
      "name": "Chocolate Chip Cookies",
      "quantity": 2,
      "price": 4.99
    }
  ],
  "buyer_email": "user@example.com",
  "currency": "USD"
}
```

**Response:**
```json
{
  "id": "cs_a1b2c3d4e5f67890",
  "status": "incomplete",
  "line_items": [
    {
      "id": "PROD-001",
      "sku": "PROD-001",
      "name": "Chocolate Chip Cookies",
      "quantity": 2,
      "price": 4.99
    }
  ],
  "totals": {
    "subtotal": 9.98,
    "tax": 0.0,
    "total": 9.98,
    "currency": "USD"
  },
  "created_at": "2026-01-18T10:30:00.000000"
}
```

**Implementation:**
```python
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid

class LineItem(BaseModel):
    id: str
    sku: str
    name: str
    quantity: int
    price: float

class CheckoutSessionCreate(BaseModel):
    line_items: List[LineItem]
    buyer_email: str
    currency: str = "USD"

class CheckoutSessionResponse(BaseModel):
    id: str
    status: str
    line_items: List[LineItem]
    totals: Dict[str, Any]
    payment: Optional[Dict[str, Any]] = None
    ap2: Optional[Dict[str, Any]] = None

# In-memory storage (use database in production)
checkout_sessions: Dict[str, Dict[str, Any]] = {}

@app.post("/ucp/v1/checkout-sessions", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: Request,
    checkout: CheckoutSessionCreate,
    session: AsyncSession = Depends(get_db)
):
    session_id = f"cs_{uuid.uuid4().hex[:16]}"

    # Calculate totals
    subtotal = sum(item.price * item.quantity for item in checkout.line_items)

    checkout_data = {
        "id": session_id,
        "status": "incomplete",
        "line_items": [item.dict() for item in checkout.line_items],
        "buyer_email": checkout.buyer_email,
        "totals": {
            "subtotal": subtotal,
            "tax": 0.0,
            "total": subtotal,
            "currency": checkout.currency
        },
        "created_at": datetime.utcnow().isoformat()
    }

    checkout_sessions[session_id] = checkout_data

    response_data = CheckoutSessionResponse(**checkout_data)
    request.state.response_data = response_data.dict()

    return response_data
```

### 2. Get Checkout Session

**Endpoint:** `GET /ucp/v1/checkout-sessions/{id}`

**Implementation:**
```python
@app.get("/ucp/v1/checkout-sessions/{session_id}", response_model=CheckoutSessionResponse)
async def get_checkout_session(
    request: Request,
    session_id: str
):
    if session_id not in checkout_sessions:
        raise HTTPException(status_code=404, detail="Checkout session not found")

    checkout_data = checkout_sessions[session_id]
    response_data = CheckoutSessionResponse(**checkout_data)
    request.state.response_data = response_data.dict()

    return response_data
```

### 3. Update Session with Payment Mandate

**Endpoint:** `PUT /ucp/v1/checkout-sessions/{id}`

**Request:**
```json
{
  "payment_mandate": {
    "payment_mandate_contents": {
      "payment_mandate_id": "PM-1A2B3C4D",
      "payment_response": {
        "details": {
          "token": "5342223122345000",
          "cryptogram": "A3F4E2C8...",
          "card_last_four": "5678",
          "card_network": "mastercard"
        }
      }
    },
    "user_authorization": "base64_signature..."
  },
  "user_signature": "base64_signature..."
}
```

**Implementation:**
```python
class CheckoutSessionUpdate(BaseModel):
    payment_mandate: Optional[Dict[str, Any]] = None
    user_signature: Optional[str] = None

@app.put("/ucp/v1/checkout-sessions/{session_id}", response_model=CheckoutSessionResponse)
async def update_checkout_session(
    request: Request,
    session_id: str,
    update: CheckoutSessionUpdate
):
    if session_id not in checkout_sessions:
        raise HTTPException(status_code=404, detail="Checkout session not found")

    checkout_data = checkout_sessions[session_id]

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
```

### 4. Complete Checkout Session

**Endpoint:** `POST /ucp/v1/checkout-sessions/{id}/complete`

**Query Parameters:**
- `otp_code` (optional): 6-digit OTP for step-up verification

**Response (Success):**
```json
{
  "status": "success",
  "checkout": {
    "id": "cs_a1b2c3d4e5f67890",
    "status": "complete",
    "receipt": {...}
  },
  "receipt": {
    "payment_mandate_id": "PM-1A2B3C4D",
    "payment_id": "PAY-ABC123",
    "amount": {"currency": "USD", "value": 9.98},
    "payment_status": {
      "merchant_confirmation_id": "MCH-XYZ789"
    }
  }
}
```

**Response (OTP Required):**
```json
{
  "status": "otp_required",
  "checkout": {
    "status": "requires_escalation",
    "otp_challenge": {
      "message": "Enter 6-digit OTP for verification",
      "payment_mandate_id": "PM-1A2B3C4D"
    }
  },
  "otp_challenge": {...}
}
```

**Implementation:**
```python
@app.post("/ucp/v1/checkout-sessions/{session_id}/complete")
async def complete_checkout_session(
    request: Request,
    session_id: str,
    otp_code: Optional[str] = None
):
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
        if not payment_agent.verify_otp(
            mandate_obj.payment_mandate_contents.payment_mandate_id,
            otp_code
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
```

---

## AP2 Integration with UCP

### Payment Token Format

**IMPORTANT**: Payment tokens must be **16-digit numeric strings** with **cryptograms**, not alphanumeric tokens.

**Correct Format:**
```json
{
  "token": "5342223122345000",
  "cryptogram": "A3F4E2C8B1D7F9E6A2C5B8D1E4F7A9C3",
  "card_last_four": "5678",
  "card_network": "VISA"
}
```

**Incorrect Format (Do NOT use):**
```json
{
  "token": "TOK-8b9f1bc1e93a4269"  // WRONG!
}
```

**Implementation:**
```python
import random
import uuid

class AP2Client:
    def _generate_token_number(self) -> str:
        """
        Generate a 16-digit token number for payment.
        Similar format to real payment systems.
        """
        return ''.join([str(random.randint(0, 9)) for _ in range(16)])

    def _generate_cryptogram(self) -> str:
        """
        Generate a random cryptogram for payment security.
        Returns a 32-character hexadecimal string.
        """
        return uuid.uuid4().hex.upper()

    def create_payment_mandate(self, cart_data, payment_card, user_email):
        # ... mandate creation logic ...

        "payment_response": {
            "details": {
                "token": self._generate_token_number(),
                "cryptogram": self._generate_cryptogram(),
                "card_last_four": payment_card.get("card_last_four"),
                "card_network": payment_card.get("card_network")
            }
        }
```

### Base64 Encoding for WebAuthn

**CRITICAL**: Use **URL-safe base64** encoding for WebAuthn credentials.

**Frontend (TypeScript):**
```typescript
// Helper function to convert ArrayBuffer to URL-safe base64
function arrayBufferToUrlSafeBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  // Standard base64 → URL-safe base64
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')
}

// Decoding challenge from backend
const base64Challenge = challenge
  .replace(/-/g, '+')
  .replace(/_/g, '/')
  .padEnd(challenge.length + (4 - (challenge.length % 4)) % 4, '=')

const challengeBuffer = Uint8Array.from(
  atob(base64Challenge),
  c => c.charCodeAt(0)
)
```

**Backend (Python):**
```python
import base64

# Always use urlsafe_b64encode/decode
credential_id = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')

# Decoding from frontend
credential_data = base64.urlsafe_b64decode(
    credential_id + '=' * (4 - len(credential_id) % 4)
)
```

---

## Implementation Patterns

### 1. UCP Client Pattern

**Discovery First:**
```python
class UCPClient:
    def __init__(self, merchant_url: str):
        self.merchant_url = merchant_url
        self.capabilities = None
        self.ucp_endpoint = None

    async def discover(self):
        """Discover merchant capabilities via UCP."""
        response = await self.client.get(
            f"{self.merchant_url}/.well-known/ucp"
        )
        ucp_profile = response.json()

        # Store capabilities
        self.capabilities = ucp_profile.get("ucp", {}).get("capabilities", [])

        # Extract service endpoint
        services = ucp_profile.get("ucp", {}).get("services", {})
        shopping_service = services.get("dev.ucp.shopping", {})
        self.ucp_endpoint = shopping_service.get("rest", {}).get("endpoint")

        return ucp_profile
```

**Use Discovered Endpoints:**
```python
    async def create_checkout_session(self, line_items, buyer_email):
        """Create UCP checkout session."""
        response = await self.client.post(
            f"{self.ucp_endpoint}/checkout-sessions",
            json={
                "line_items": line_items,
                "buyer_email": buyer_email,
                "currency": "USD"
            }
        )
        return response.json()
```

### 2. Request/Response Logging Pattern

**Using request.state for Logging:**

```python
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json

class RequestLoggingMiddleware(BaseHTTPMiddleware):
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
        duration_ms = (time.time() - start_time) * 1000

        # Get response body from request.state (set by endpoints)
        response_body = getattr(request.state, "response_data", None)

        # Log to database...

        return response
```

**In Endpoints:**
```python
@app.post("/ucp/v1/checkout-sessions")
async def create_checkout_session(request: Request, ...):
    # ... business logic ...

    response_obj = CheckoutSessionResponse(...)

    # IMPORTANT: Store response in request.state for logging middleware
    request.state.response_data = response_obj.dict()

    return response_obj
```

### 3. Database Schema Pattern

**UCP Request Logs:**
```python
from sqlalchemy import Column, String, Integer, Float, Text, DateTime
from datetime import datetime

class UCPRequestLog(Base):
    __tablename__ = "ucp_request_logs"

    id = Column(String, primary_key=True)
    endpoint = Column(String, nullable=False, index=True)
    method = Column(String, nullable=False)
    query_params = Column(Text)
    request_body = Column(Text)
    response_status = Column(Integer, nullable=False)
    response_body = Column(Text)  # Full response JSON
    client_ip = Column(String)
    user_agent = Column(String)
    duration_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
```

**Payment Mandate with UCP Session ID:**
```python
class PaymentMandate(Base):
    __tablename__ = "payment_mandates"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    checkout_session_id = Column(String)  # UCP checkout session ID
    mandate_data = Column(Text)  # JSON: Full AP2 PaymentMandate
    user_signature = Column(Text)  # WebAuthn signature
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    signed_at = Column(DateTime)
    completed_at = Column(DateTime)
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Direct AP2 Endpoints

**❌ Wrong Pattern:**
```python
# Direct AP2 endpoints (non-UCP compliant)
@app.post("/ap2/payment/process")
async def process_payment(mandate: AP2PaymentMandate):
    ...
```

**✅ Correct Pattern:**
```python
# AP2 wrapped behind UCP checkout
@app.post("/ucp/v1/checkout-sessions/{id}/complete")
async def complete_checkout_session(session_id: str, otp_code: Optional[str] = None):
    # AP2 processing happens internally
    payment_agent.process_payment(mandate)
```

### Pitfall 2: Wrong Token Format

**❌ Wrong:**
```python
"token": f"TOK-{uuid.uuid4().hex[:16]}"  # Alphanumeric
```

**✅ Correct:**
```python
"token": ''.join([str(random.randint(0, 9)) for _ in range(16)])  # 16 digits
"cryptogram": uuid.uuid4().hex.upper()  # 32-char hex
```

### Pitfall 3: Base64 Encoding Mismatch

**❌ Wrong:**
```typescript
// Frontend uses standard base64
btoa(binary)  // Results in + / = characters
```

**✅ Correct:**
```typescript
// Frontend uses URL-safe base64
btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
```

### Pitfall 4: Response Logging with Streaming

**❌ Wrong:**
```python
# Trying to read response.body (doesn't work with StreamingResponse)
response_body = await response.body()
```

**✅ Correct:**
```python
# Store in request.state before returning
request.state.response_data = response_obj.dict()
# Middleware reads from request.state
```

### Pitfall 5: Missing UCP Headers

**✅ Always include:**
```python
headers = {
    "Content-Type": "application/json",
    "UCP-Agent": "MyAgent/1.0"  # Recommended
}
```

### Pitfall 6: Database Migration

**❌ Wrong:**
```python
# Adding new column without migration
class PaymentMandate(Base):
    checkout_session_id = Column(String)  # New field
    # Old database won't have this column!
```

**✅ Correct:**
```python
# Either:
# 1. Delete old database and recreate
rm chat_app.db
# Service restart creates new schema

# Or:
# 2. Add column with ALTER TABLE
cursor.execute("ALTER TABLE payment_mandates ADD COLUMN checkout_session_id TEXT;")
```

---

## Testing & Debugging

### Test UCP Discovery

```bash
# Test discovery endpoint
curl http://localhost:8453/.well-known/ucp | jq

# Verify it returns:
# - version: "2026-01-11"
# - services.dev.ucp.shopping.rest.endpoint
# - capabilities with checkout and product_search
```

### Test Product Search

```bash
curl "http://localhost:8453/ucp/products/search?q=cookies&limit=5" | jq
```

### Test Complete Checkout Flow

```bash
# 1. Create session
SESSION_ID=$(curl -X POST http://localhost:8453/ucp/v1/checkout-sessions \
  -H "Content-Type: application/json" \
  -d '{
    "line_items": [{"id":"PROD-001","sku":"PROD-001","name":"Cookies","quantity":2,"price":4.99}],
    "buyer_email": "test@example.com",
    "currency": "USD"
  }' | jq -r '.id')

# 2. Get session
curl http://localhost:8453/ucp/v1/checkout-sessions/$SESSION_ID | jq

# 3. Update with mandate (requires real mandate)
curl -X PUT http://localhost:8453/ucp/v1/checkout-sessions/$SESSION_ID \
  -H "Content-Type: application/json" \
  -d '{"payment_mandate": {...}, "user_signature": "..."}' | jq

# 4. Complete
curl -X POST http://localhost:8453/ucp/v1/checkout-sessions/$SESSION_ID/complete | jq
```

### Debug Logs

```bash
# Watch merchant backend logs
tail -f logs/merchant-backend.log | grep -E "UCP|checkout"

# Watch chat backend logs
tail -f logs/chat-backend.log | grep -E "UCP|payment"

# Check for errors
tail -100 logs/merchant-backend.log | grep -i error
```

### Dashboard Monitoring

Access dashboard at: `http://localhost:8451/dashboard` (or `https://app.abhinava.xyz/dashboard`)

Features:
- View all UCP requests (product search, checkout sessions)
- View all AP2 payment messages with signatures
- Real-time monitoring
- Clear logs button

---

## Production Considerations

### 1. Database Migration Strategy

**Development:**
```bash
# Delete and recreate (data loss OK)
rm *.db
# Restart service - auto-creates schema
```

**Production:**
```python
# Use proper migrations (Alembic)
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('payment_mandates',
        sa.Column('checkout_session_id', sa.String(), nullable=True))

def downgrade():
    op.drop_column('payment_mandates', 'checkout_session_id')
```

### 2. Session Storage

**Development:**
```python
# In-memory dict
checkout_sessions: Dict[str, Dict[str, Any]] = {}
```

**Production:**
```python
# Database or Redis
class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"
    id = Column(String, primary_key=True)
    status = Column(String)
    data = Column(JSON)
    created_at = Column(DateTime)
    expires_at = Column(DateTime)
```

### 3. Security Hardening

```python
# CORS - restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://chat.yourdomain.com"],  # Specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

# Rate limiting
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/ucp/v1/checkout-sessions")
@limiter.limit("10/minute")
async def create_checkout_session(...):
    ...

# HTTPS only
if not request.url.scheme == "https":
    raise HTTPException(status_code=403, detail="HTTPS required")
```

### 4. Monitoring & Alerts

```python
# Log all UCP interactions
logger.info(f"UCP checkout created: {session_id}", extra={
    "session_id": session_id,
    "buyer_email": buyer_email,
    "total": total,
    "ip": request.client.host
})

# Metrics
from prometheus_client import Counter, Histogram

checkout_created = Counter('ucp_checkout_created', 'Checkout sessions created')
checkout_duration = Histogram('ucp_checkout_duration', 'Checkout completion time')
```

### 5. Error Handling

```python
from fastapi import HTTPException
from pydantic import ValidationError

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request", "details": str(exc)}
    )

@app.post("/ucp/v1/checkout-sessions")
async def create_checkout_session(...):
    try:
        # ... business logic ...
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Checkout creation failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## Quick Reference

### UCP Endpoints Checklist

- [ ] `GET /.well-known/ucp` - Discovery endpoint
- [ ] `GET /ucp/products/search` - Product search
- [ ] `POST /ucp/v1/checkout-sessions` - Create checkout
- [ ] `GET /ucp/v1/checkout-sessions/{id}` - Get checkout
- [ ] `PUT /ucp/v1/checkout-sessions/{id}` - Update checkout
- [ ] `POST /ucp/v1/checkout-sessions/{id}/complete` - Complete checkout

### AP2 Integration Checklist

- [ ] 16-digit numeric tokens (not alphanumeric)
- [ ] Cryptograms included in payment details
- [ ] URL-safe base64 encoding for WebAuthn
- [ ] Payment mandates processed internally (not exposed)
- [ ] OTP support via query parameter
- [ ] checkout_session_id stored in payment mandate table

### Logging Checklist

- [ ] Response data stored in `request.state.response_data`
- [ ] Middleware reads from `request.state`
- [ ] UCP and AP2 logs separated
- [ ] Request/response bodies captured
- [ ] Timing metrics recorded

---

## Version History

- **2026-01-18**: Initial knowledge base created based on production implementation
- **2026-01-11**: UCP version used in implementation

---

## References

- UCP Specification: https://ucp.dev/specification/
- UCP Checkout: https://ucp.dev/specification/checkout
- UCP REST Binding: https://ucp.dev/specification/checkout-rest/
- AP2 Mandates Extension: https://ucp.dev/documentation/ucp-and-ap2/

---

**Note**: This knowledge base is based on actual production implementation experience and contains patterns that have been proven to work. Always refer to the official UCP specification for the most up-to-date information.
