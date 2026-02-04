# Enhanced Business Agent - Split Architecture with UCP + AP2

Note: This is forked from https://github.com/abhinavasr/ucp-sample

This is a implementation demonstrating **two separate systems** communicating over the **Universal Commerce Protocol (UCP)** for product discovery and the **Agentic Payment Protocol (AP2)** for secure payment processing.

## 🏗️ Architecture Overview

The application is split into two independent backends that communicate via UCP:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                          │
├──────────────────────────────┬──────────────────────────────────┤
│  Chat Frontend (Port 3000)   │  Merchant Portal (Port 3001)     │
│  - React + TypeScript        │  - React + TypeScript            │
│  - Tailwind CSS              │  - Tailwind CSS                  │
│  - Vite Dev Server           │  - Vite Dev Server               │
└──────────────┬───────────────┴──────────────┬───────────────────┘
               │                              │
               │ HTTP                         │ HTTP
               │                              │
┌──────────────▼───────────────┐  ┌──────────▼───────────────────┐
│   Chat Backend (Port 8452)   │  │ Merchant Backend (Port 8453) │
│   ========================   │  │ ===========================  │
│   • UCP Client               │  │ • UCP Server                 │
│   • AP2 Consumer Agent       │  │ • AP2 Merchant Agent         │
│   • Credentials Provider     │  │ • Payment Processor          │
│   • FastAPI                  │  │ • FastAPI                    │
│   • Ollama LLM Integration   │  │ • Ollama (Merchant Agent)    │
│   • Shopping Assistant       │  │ • SQLite Database            │
│   • WebAuthn Passkeys        │  │ • Product Catalog            │
│   • Encrypted Card Storage   │  │ • CRUD API                   │
│   • Logout Feature           │  │ • Request Logging            │
└──────────────┬───────────────┘  └──────────┬────────────────|──┘
               │                              │               |
               │    UCP REST Protocol         │               | 1.Startup: Create Did:web Wallet & Host did Doc
               │    /.well-known/ucp          │               | /.well-known/did.json
               │    /ucp/v1/checkout-sessions │               | 2.Checkout: Sign Cart Mandate with Wallet
               │    /ucp/products/search      │               | 3.Payment: Verify Mandate
               │                              │               |
               │    AP2 via UCP Checkout      │               │
               │    (No direct AP2 endpoints) │               │
               └──────────────────────────────┘               │
                                                              │
                                                ┌─────────────|────────────────
                                                │ Signer Service (Port 8454)   │
                                                │ ===========================  │
                                                │ • DID:web Wallet Management  │
                                                │ • JWT-VC Signing (Affinidi)  │
                                                │ • Credential Verification    │
                                                │                              │
                                                │ 🔐 Endpoints:                │
                                                │ 1. POST /api/did-web-generate│
                                                │ 2. POST /api/sign-credential │
                                                │ 3. POST /api/verify-credential
                                                └────────────┬─────────────────┘
                                                             │
                                                             │ Affinidi TDK
                                                             │ (Wallets + Signing + Verification)
                                                             ▼
                                                ┌────────────────────────────────┐
                                                │   Affinidi Infrastructure      │
                                                │   =========================    │
                                                │ • DID:web Registry             │
                                                │ • Key Management (Signing)     │
                                                │ • JWT-VC Signing/Verification  │
                                                └────────────────────────────────┘

```

### Key Components

#### 1. **Chat Backend** (Port 8452) - UCP Client + AP2 Consumer Agent

- **Role**: Consumer/Client + Credentials Provider
- **Technology**: FastAPI + Ollama LLM + SQLAlchemy + Cryptography
- **Responsibilities**:
  - AI-powered chat interface with Ollama
  - Natural language processing for shopping
  - Shopping cart management
  - **UCP Client**: Discovers and queries merchant backend for products
  - **AP2 Consumer Agent**: Creates and signs payment mandates
  - **Credentials Provider**: Stores user accounts, payment cards (encrypted), and passkeys
  - WebAuthn/FIDO2 passkey authentication
  - Payment mandate creation and signing
  - **[OPTIONAL] Mastercard Integration**: Card tokenization and authentication (disabled by default)
  - Separate SQLite database for user credentials (`chat_app.db`)

#### 2. **Merchant Backend** (Port 8453) - UCP Server + AP2 Merchant Agent

- **Role**: Provider/Server + Payment Processor
- **Technology**: FastAPI + SQLAlchemy + SQLite + Ollama
- **Responsibilities**:
  - Product catalog management
  - Database persistence for products
  - **UCP Server**: Exposes `.well-known/ucp` discovery and `/ucp/products/search`
  - **AP2 Merchant Agent**: Processes payment mandates with Ollama-powered decision making
  - Payment validation and processing
  - OTP challenge generation (10-30% of transactions)
  - Payment receipt issuance
  - Separate SQLite database for products (`enhanced_app.db`)
  - **Security**: Never stores or sees raw payment card numbers (token-based only)

#### 3. **Frontend Applications**

- **Chat Frontend** (Port 8450): Customer-facing shopping interface with registration, checkout, and passkey auth
- **Merchant Portal** (Port 8451): Admin interface for product management

## 🔌 UCP Integration

### UCP Discovery Endpoint

The Merchant Backend exposes a standard UCP discovery endpoint:

```bash
GET http://localhost:8451/.well-known/ucp
```

**Response:**

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

### UCP Product Search

The Chat Backend uses the UCP client to search products:

```python
# In chat-backend/ucp_client.py
async def search_products(self, query: str = None, limit: int = 10):
    """Search products using UCP product search endpoint."""
    response = await self.client.get(
        f"{self.merchant_url}/ucp/products/search",
        params={"q": query, "limit": limit}
    )
    # Prices are in cents (UCP standard)
    data = response.json()
    return data["items"]
```

The Merchant Backend serves UCP-compliant product data:

```bash
GET http://localhost:8451/ucp/products/search?q=cookies&limit=5
```

**Response:**

```json
{
  "items": [
    {
      "id": "PROD-001",
      "title": "Chocochip Cookies",
      "price": 499, // Price in cents
      "image_url": "...",
      "description": "Delicious chocolate chip cookies"
    }
  ],
  "total": 1
}
```

### UCP Checkout Sessions (AP2 Integration)

The merchant backend exposes UCP checkout endpoints that wrap AP2 payment processing per the UCP specification:

```bash
# Create checkout session
POST http://localhost:8453/ucp/v1/checkout-sessions
{
  "line_items": [
    {"id": "PROD-001", "sku": "PROD-001", "name": "Cookies", "quantity": 2, "price": 4.99}
  ],
  "buyer_email": "user@example.com",
  "currency": "SGD"
}

# Response
{
  "id": "cs_a1b2c3d4e5f67890",
  "status": "incomplete",
  "line_items": [...],
  "totals": {"subtotal": 9.98, "tax": 0.0, "total": 9.98, "currency": "SGD"}
}

# Update session with AP2 payment mandate
PUT http://localhost:8453/ucp/v1/checkout-sessions/{id}
{
  "payment_mandate": {...},  // AP2 payment mandate
  "user_signature": "..."     // WebAuthn signature
}

# Complete checkout (processes payment via AP2)
POST http://localhost:8453/ucp/v1/checkout-sessions/{id}/complete
# Optional: ?otp_code=123456 for OTP verification

# Response
{
  "status": "success",
  "checkout": {...},
  "receipt": {...}  // AP2 payment receipt
}
```

**Key Features:**

- ✅ **UCP Compliant**: Follows https://ucp.dev/specification/checkout
- ✅ **AP2 Integration**: Payment mandates processed via AP2 agent internally
- ✅ **Session Management**: Stateful checkout with status transitions
- ✅ **OTP Support**: Handles step-up authentication via query parameter

## 💳 AP2 Payment Protocol Integration

This application implements the **Agentic Payment Protocol (AP2)** for secure, passkey-authenticated payments.

### AP2 Architecture

The payment flow follows AP2 specification with clear separation between consumer agent (credentials provider) and merchant agent (payment processor):

```
User Registration Flow:
1. User → Chat Frontend: Register with email + display name
2. Chat Frontend → Browser: Trigger WebAuthn passkey creation
3. Browser: Create FIDO2 credential
4. Chat Frontend → Chat Backend: /api/auth/register (email, passkey credential)
5. Chat Backend: Store user + encrypted default card (5123 1212 2232 5678)

Payment Flow (via UCP Checkout):
1. User → Chat Frontend: "I want to checkout"
2. Chat Frontend → Chat Backend: POST /api/payment/prepare-checkout
3. Chat Backend → Merchant Backend: POST /ucp/v1/checkout-sessions (create UCP session)
4. Chat Backend: Create unsigned AP2 payment mandate, store session ID
5. Chat Frontend → User: Show checkout popup (cart, masked card, total)
6. User → Chat Frontend: Click "Confirm Payment with Passkey"
7. Chat Frontend → Browser: Request WebAuthn assertion
8. Browser: User authenticates with biometrics
9. Chat Frontend → Chat Backend: POST /api/payment/confirm-checkout (signed mandate)
10. Chat Backend → Merchant Backend: PUT /ucp/v1/checkout-sessions/{id} (attach mandate)
11. Chat Backend → Merchant Backend: POST /ucp/v1/checkout-sessions/{id}/complete
12. Merchant Backend (AP2 Agent): Validate signature, check fraud risk
13a. If low risk → Payment approved → Receipt returned with status "success"
13b. If high risk → OTP challenge → Receipt with status "otp_required"
14. (If OTP) User → Chat Frontend: Enter 6-digit OTP
15. Chat Frontend → Chat Backend: POST /api/payment/verify-otp
16. Chat Backend → Merchant Backend: POST /ucp/v1/checkout-sessions/{id}/complete?otp_code=123456
17. Merchant Backend: Verify OTP → Process payment → Receipt
18. Chat Frontend: Show success confirmation in chat history with payment ID
```

### API Endpoints

#### Chat Backend (Consumer Agent)

```bash
# Authentication & Registration
POST /api/auth/challenge           # Get WebAuthn challenge
POST /api/auth/register            # Register user with passkey + default card
POST /api/auth/verify-passkey      # Verify passkey signature

# Payment Card Management
GET /api/payment/cards             # List user's payment cards (masked)
GET /api/payment/cards/default     # Get default payment card

# Payment Flow (uses UCP checkout internally)
POST /api/payment/prepare-checkout # Create UCP session + AP2 mandate
POST /api/payment/confirm-checkout # Sign mandate, complete UCP checkout
POST /api/payment/verify-otp       # Complete checkout with OTP

# Database Management
POST /api/database/reset           # Reset database (clear all user data)
```

#### Merchant Backend (UCP Server + AP2 Merchant Agent)

```bash
# UCP Checkout Endpoints (wrapping AP2)
POST   /ucp/v1/checkout-sessions          # Create checkout session
GET    /ucp/v1/checkout-sessions/{id}     # Get checkout session
PUT    /ucp/v1/checkout-sessions/{id}     # Update with payment mandate
POST   /ucp/v1/checkout-sessions/{id}/complete  # Process payment via AP2

# Dashboard API
GET    /api/dashboard/ucp-logs     # UCP request logs
GET    /api/dashboard/ap2-logs     # AP2 payment logs
GET    /api/dashboard/stats        # Dashboard statistics
DELETE /api/dashboard/clear-logs   # Clear all logs
```

### AP2 Payment Mandate Structure

```json
{
  "payment_mandate_contents": {
    "payment_mandate_id": "PM-1A2B3C4D5E6F7890",
    "timestamp": "2026-01-17T10:30:00.000000",
    "payment_details_id": "REQ-A1B2C3D4E5F6",
    "payment_details_total": {
      "label": "Total",
      "amount": {
        "currency": "SGD",
        "value": 15.99
      }
    },
    "payment_response": {
      "request_id": "REQ-A1B2C3D4E5F6",
      "method_name": "CARD",
      "details": {
        "token": "5342223122345000",
        "cryptogram": "A3F4E2C8B1D7F9E6A2C5B8D1E4F7A9C3",
        "card_last_four": "5678",
        "card_network": "mastercard"
      },
      "payer_email": "user@example.com",
      "payer_name": "John Doe"
    },
    "merchant_agent": "merchant-001"
  },
  "user_authorization": "base64_encoded_passkey_signature"
}
```

### AP2 Payment Receipt

**Success:**

```json
{
  "payment_mandate_id": "PM-1A2B3C4D5E6F7890",
  "payment_id": "PAY-ABC123456789",
  "amount": { "currency": "SGD", "value": 15.99 },
  "payment_status": {
    "status_code": "SUCCESS",
    "message": "Payment processed successfully"
  },
  "timestamp": "2026-01-17T10:30:05.000000"
}
```

**OTP Challenge:**

```json
{
  "payment_mandate_id": "PM-1A2B3C4D5E6F7890",
  "payment_status": {
    "error_message": "OTP_REQUIRED:Additional verification required. Please enter the 6-digit OTP code."
  },
  "payment_method_details": {
    "otp_challenge": {
      "payment_mandate_id": "PM-1A2B3C4D5E6F7890",
      "message": "Enter 6-digit OTP for verification"
    }
  }
}
```

### Security Features

1. **WebAuthn Passkey Authentication** (FIDO2)
   - Biometric authentication (fingerprint/face)
   - No passwords stored
   - Phishing-resistant

2. **Encrypted Card Storage** (Fernet symmetric encryption)
   - Card numbers encrypted at rest
   - Only decrypted for payment processing
   - Merchant never sees raw card numbers

3. **Token-Based Payment**
   - Opaque tokens sent to merchant
   - Merchant only sees: last 4 digits, card network, token
   - Full card number stays with consumer agent

4. **OTP Challenge** (Risk-Based)
   - 10% probability for amounts < $100
   - 30% probability for amounts ≥ $100
   - Additional verification layer

5. **Separation of Credentials**
   - Consumer agent stores: users, cards, passkeys
   - Merchant agent stores: products only
   - Zero trust architecture

6. **[OPTIONAL] Mastercard Network Tokenization**
   - Card-on-File tokenization replaces PAN with network token
   - Secure Card-on-File authentication adds risk-based challenges
   - OAuth 1.0a signed requests with RSA-SHA256
   - Fully optional - disabled by default

## 💳 Mastercard Integration Logic (Optional)

### Overview

The application includes **optional** integration with Mastercard's Card on File (CoF) and Secure Card on File (SCoF) APIs. This feature is **disabled by default** and the app works completely without it.

**When enabled**, Mastercard APIs add two enhancements:

1. **Tokenization** - During registration, card numbers are replaced with network tokens
2. **Authentication** - During payment, additional risk-based authentication may be required

### Registration Flow with Mastercard

```
Standard Flow (MASTERCARD_ENABLED=false):
───────────────────────────────────────────
1. User provides email + display name
2. Browser creates WebAuthn passkey
3. Chat backend creates User record
4. Chat backend creates PaymentCard with encrypted card number
5. Registration complete

Enhanced Flow (MASTERCARD_ENABLED=true):
────────────────────────────────────────────
1. User provides email + display name
2. Browser creates WebAuthn passkey
3. Chat backend creates User record
4. Chat backend creates PaymentCard with encrypted card number
5. Chat backend calls Mastercard Tokenization API
   └─ POST https://sandbox.api.mastercard.com/mdes/digitization/tokenize
   └─ OAuth 1.0a signed request
6. If successful:
   └─ Store network token in payment_card.mastercard_token
   └─ Set payment_card.is_tokenized = True
7. If failed:
   └─ Log error
   └─ Continue with encrypted card (fallback)
8. Registration complete
```

**Code Location:** [chat-backend/main.py:484-506](chat-backend/main.py#L484-L506)

### Payment Flow with Mastercard

```
Standard Flow (MASTERCARD_ENABLED=false or card not tokenized):
───────────────────────────────────────────────────────────────
1. User clicks "Confirm Payment with Passkey"
2. Browser collects WebAuthn signature
3. Chat backend signs payment mandate
4. Chat backend sends mandate to merchant via UCP
5. Merchant processes payment
6. [Optional] Standard OTP challenge (10-30% probability)
7. Payment complete

Enhanced Flow (MASTERCARD_ENABLED=true and card.is_tokenized=True):
───────────────────────────────────────────────────────────────────
1. User clicks "Confirm Payment with Passkey"
2. Browser collects WebAuthn signature
3. Chat backend checks if card is tokenized
4. Chat backend calls Mastercard Authentication API
   └─ POST https://sandbox.api.mastercard.com/scof/authenticate
   └─ Passes: network token, amount, merchant ID
5. Mastercard risk engine evaluates transaction
6. If authentication required:
   ├─ Create MastercardAuthenticationChallenge record
   ├─ Return OTP challenge to user
   ├─ User enters 6-digit code
   ├─ POST /api/payment/verify-mastercard-auth
   └─ Verify code with Mastercard API
7. If authentication approved or not required:
   └─ Continue to step 8
8. Chat backend signs payment mandate
9. Chat backend sends mandate to merchant via UCP
10. Merchant processes payment
11. [Optional] Standard OTP challenge (separate from Mastercard)
12. Payment complete
```

**Code Locations:**

- Initial auth check: [chat-backend/main.py:807-856](chat-backend/main.py#L807-L856)
- Verification endpoint: [chat-backend/main.py:1021-1156](chat-backend/main.py#L1021-L1156)

### Database Schema Extensions

When Mastercard is enabled, the following database changes are made:

**PaymentCard table additions:**

```python
mastercard_token = Column(String)              # Network token (e.g., "4111111111111111")
mastercard_token_ref = Column(String)          # Unique reference (e.g., "DWSPMC000...")
mastercard_token_assurance = Column(String)    # Assurance level ("high", "medium", "low")
tokenization_date = Column(DateTime)           # When tokenization occurred
is_tokenized = Column(Boolean, default=False)  # Flag indicating tokenization status
```

**New table: mastercard_auth_challenges**

```python
id = Column(String, primary_key=True)
payment_mandate_id = Column(String, ForeignKey("payment_mandates.id"))
challenge_id = Column(String)                  # Mastercard's challenge ID
transaction_id = Column(String)                # UCP checkout session ID
authentication_method = Column(String)         # "otp", "biometric", "none"
status = Column(String)                        # "pending", "approved", "declined", "expired"
verification_code = Column(String)             # Temporary OTP storage
attempts = Column(Integer, default=0)          # Failed attempts counter
created_at = Column(DateTime)
verified_at = Column(DateTime)
expires_at = Column(DateTime)                  # Challenges expire in 5 minutes
raw_response = Column(Text)                    # Full API response (JSON)
```

**Schema Location:** [chat-backend/database.py](chat-backend/database.py)

### Fallback Behavior

The Mastercard integration is designed to **never break** the payment flow:

| Scenario                 | Behavior                                   |
| ------------------------ | ------------------------------------------ |
| MASTERCARD_ENABLED=false | Uses encrypted card storage, no API calls  |
| Invalid credentials      | Logs error, uses encrypted card storage    |
| Tokenization fails       | Logs error, continues with encrypted card  |
| Authentication API error | Logs error, proceeds to payment            |
| Verification timeout     | Challenge expires, user can retry checkout |

**All errors are caught and logged** - the payment flow always continues.

### OAuth 1.0a Signature Process

Mastercard APIs require OAuth 1.0a with RSA-SHA256 signatures:

```python
# 1. Generate OAuth parameters
oauth_params = {
    "oauth_consumer_key": MASTERCARD_CONSUMER_KEY,
    "oauth_nonce": random_32_char_string(),
    "oauth_timestamp": unix_timestamp(),
    "oauth_signature_method": "RSA-SHA256",
    "oauth_version": "1.0",
    "oauth_body_hash": base64(sha256(request_body))
}

# 2. Create signature base string
base_string = f"{method}&{url_encoded}&{params_encoded}"

# 3. Sign with private key
signature = rsa_sign_sha256(private_key, base_string)
oauth_params["oauth_signature"] = base64(signature)

# 4. Add Authorization header
headers["Authorization"] = f'OAuth {format_oauth_params(oauth_params)}'
```

**Implementation:** [chat-backend/mastercard_client.py:77-140](chat-backend/mastercard_client.py)

### Testing Mastercard Integration

**1. Get sandbox credentials:**

- Sign up at https://developer.mastercard.com/
- Create project for "Card on File" and "Secure Card on File"
- Download consumer key and signing key (.p12)
- Convert to .pem: `openssl pkcs12 -in key.p12 -out key.pem -nodes`

**2. Configure environment:**

```bash
# Edit chat-backend/.env
MASTERCARD_ENABLED=true
MASTERCARD_CONSUMER_KEY=your_consumer_key_here
MASTERCARD_SIGNING_KEY_PATH=/absolute/path/to/signing-key.pem
MASTERCARD_SANDBOX=true
```

**3. Restart and test:**

```bash
./stop-split.sh && ./start-split.sh

# Watch logs for Mastercard activity
tail -f chat-backend/chat-backend.log | grep -i mastercard
```

**4. Expected log output:**

```
INFO:     Mastercard API integration enabled
INFO:main:Tokenizing card for user test@example.com with Mastercard API
INFO:main:Card tokenized successfully for test@example.com: DWSPMC000...
INFO:main:Initiating Mastercard authentication for mandate PM-ABC123
INFO:main:Mastercard authentication required: otp
INFO:main:Mastercard authentication verified, payment successful
```

### Documentation

For complete Mastercard integration documentation, see:

- **[Mastercard Integration Guide](MASTERCARD_INTEGRATION.md)** - Full setup and API reference
- **[Mastercard Setup Guide](MASTERCARD_SETUP.md)** - Step-by-step credential setup
- **[Mastercard Developer Portal](https://developer.mastercard.com/)** - Official API docs

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+**
2. **Node.js 18+**
3. **Ollama** running with a model (e.g., qwen3:8b, qwen2.5:latest, gemma2:latest)

### Installation & Running

1. **Clone the repository**

   ```bash
   git clone https://github.com/kamarthiparamesh/ap2-ucp-sample.git
   cd ap2-ucp-sample
   ```

2. **Configure environment**

   Copy the example environment files and configure them:

   ```bash
   # Copy environment files from examples
   cp chat-backend/.env.example chat-backend/.env
   cp merchant-backend/.env.example merchant-backend/.env
   cp signer-server/.env.example signer-server/.env

   # Edit chat-backend/.env
   OLLAMA_URL=http://192.168.86.41:11434
   OLLAMA_MODEL=qwen3:8b
   MERCHANT_BACKEND_URL=http://localhost:8453

   # Edit merchant-backend/.env
   DATABASE_URL=sqlite+aiosqlite:///./merchant.db
   PORT=8453
   ```

3. **Set up ngrok for merchant backend** (required for external access)

   Create an ngrok tunnel with your domain pointing to the merchant backend:

   ```bash
   ngrok http --url=marmot-suited-muskrat.ngrok-free.app 8453
   ```

   Then update the merchant backend environment file:

   ```bash
   # Edit merchant-backend/.env
   MERCHANT_DOMAIN=marmot-suited-muskrat.ngrok-free.app
   ```

   > **Note:** Replace `marmot-suited-muskrat.ngrok-free.app` with your actual ngrok domain.

4. **Start all services**

   ```bash
   ./start-split.sh
   ```

   This will:
   - Activate Python virtual environments with all dependencies (httpx, fastapi, etc.)
   - Start Chat Backend (8452) - UCP Client + AP2 Consumer Agent
   - Start Merchant Backend (8453) - UCP Server + AP2 Merchant Agent
   - Start Signer Server (8454) - DID:web Wallet & Signing Service
   - Start Chat Frontend (8450) - Customer Interface
   - Start Merchant Portal (8451) - Admin Interface
   - Create log files for each service

5. **Access the applications**
   - **Chat Interface**: http://localhost:8450 (https://chat.abhinava.xyz)
   - **Merchant Portal**: http://localhost:8451 (https://app.abhinava.xyz)
   - **Chat Backend API**: http://localhost:8452/docs
   - **Merchant Backend API**: http://localhost:8453/docs
   - **Signer Server API**: http://localhost:8454/docs

6. **Register your first user**
   - Visit http://localhost:8450
   - Click "Register" button
   - Enter your email and name
   - Create a passkey using your device's biometric authentication
   - A default Mastercard (ending in 5678) will be automatically added

7. **Stop all services**

   When you're done, stop all running services:

   ```bash
   ./stop-split.sh
   ```

8. **[OPTIONAL] Enable Mastercard Integration**

   The application supports optional Mastercard Card on File tokenization and Secure Card on File authentication. This is **disabled by default** and the app works fully without it.

   **Key Features:**
   - Card tokenization during registration (replaces PAN with network token)
   - Additional authentication layer during checkout (OTP/biometric)
   - OAuth 1.0a signed API requests to Mastercard sandbox/production
   - Fallback to encrypted card storage if tokenization fails

   **To enable:**

   ```bash
   # Edit chat-backend/.env
   MASTERCARD_ENABLED=true
   MASTERCARD_CONSUMER_KEY=your_consumer_key_from_mastercard_portal
   MASTERCARD_SIGNING_KEY_PATH=/absolute/path/to/signing-key.pem
   MASTERCARD_SANDBOX=true  # Use sandbox for testing
   ```

   **Code References:**
   - Mastercard Client: [chat-backend/mastercard_client.py](chat-backend/mastercard_client.py)
   - Tokenization Logic: [chat-backend/main.py:484-506](chat-backend/main.py#L484-L506)
   - Authentication Logic: [chat-backend/main.py:807-856](chat-backend/main.py#L807-L856)
   - Database Models: [chat-backend/database.py:49-55, 164-193](chat-backend/database.py#L49-L55)
   - API endpoint reference
   - Testing and troubleshooting

9. **Stop all services**
   ```bash
   ./stop-split.sh
   ```

### Troubleshooting

#### Database Schema Issues

If you encounter database errors (like "table has no column"), the database schema may be outdated:

**Option 1: Use the Reset Database feature (recommended for development)**

1. Visit http://localhost:8450
2. Click "Reset DB" button in the navigation menu
3. Confirm the action
4. This will clear all user data, payment cards, mandates, and transactions

**Option 2: Manually delete database files**

```bash
# Stop services
./stop-split.sh

# Remove old databases
rm chat-backend/chat_app.db
rm merchant-backend/merchant.db

# Restart services (databases will be recreated automatically)
./start-split.sh
```

#### Missing Dependencies

If you see `ModuleNotFoundError: No module named 'httpx'` or similar errors, ensure services are started with the `start-split.sh` script, which activates the virtual environments:

```bash
# Don't run: python3 main.py directly
# Do run: ./start-split.sh (from repository root)
```

## 📁 Project Structure

```
ap2-ucp-sample/
├── start-split.sh            # Start all services (with venv activation)
├── stop-split.sh             # Stop all services cleanly
│
├── chat-backend/              # UCP Client Backend
│   ├── main.py               # FastAPI application
│   ├── ollama_agent.py       # LLM-powered agent
│   ├── ucp_client.py         # UCP REST client
│   ├── database.py           # User credentials & payment cards
│   ├── payment_utils.py      # WebAuthn, encryption, OTP
│   ├── ap2_client.py         # AP2 consumer agent client
│   ├── mastercard_client.py  # Optional Mastercard integration
│   ├── .env                  # Configuration
│   ├── pyproject.toml        # Python dependencies
│   ├── venv/                 # Python virtual environment
│   └── chat_app.db           # SQLite database (auto-created)
│
├── merchant-backend/          # UCP Server Backend
│   ├── main.py               # FastAPI application with UCP
│   ├── database.py           # SQLAlchemy models (products)
│   ├── .env                  # Configuration
│   ├── pyproject.toml        # Python dependencies
│   ├── venv/                 # Python virtual environment
│   └── merchant.db           # SQLite database (auto-created)
│
├── frontend/
│   ├── chat/                 # Chat Frontend (Port 8450)
│   │   ├── src/
│   │   │   ├── App.tsx      # React application
│   │   │   └── RegisterPage.tsx  # Passkey registration
│   │   └── vite.config.ts   # Proxy to chat-backend
│   │
│   └── merchant-portal/      # Admin Frontend (Port 8451)
│       ├── src/
│       │   └── App.tsx      # React application
│       └── vite.config.ts   # Proxy to merchant-backend
│
├── README.md                 # This file
├── MASTERCARD_INTEGRATION.md # Mastercard API setup guide
└── UCP-KNOWLEDGE-BASE.md     # UCP protocol documentation
```

## 🔍 Testing UCP Communication

### 1. Test UCP Discovery

```bash
# Discover merchant capabilities
curl http://localhost:8453/.well-known/ucp | jq
```

### 2. Test UCP Product Search

```bash
# Search for cookies
curl "http://localhost:8453/ucp/products/search?q=cookies&limit=5" | jq
```

### 3. Test Chat Backend UCP Client

```bash
# The chat backend automatically uses UCP to fetch products
curl -X POST http://localhost:8452/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me cookies available",
    "session_id": "test-session"
  }' | jq
```

The chat backend will:

1. Detect product search intent
2. Call merchant backend via UCP: `GET /ucp/products/search?q=cookies`
3. Convert UCP format (cents) to dollars
4. Send product context to LLM
5. Return AI-generated response with product recommendations

## 🎯 Key Features

### UCP Communication

- ✅ **Discovery**: Chat backend discovers merchant capabilities via `/.well-known/ucp`
- ✅ **Standard Protocol**: UCP-compliant REST endpoints following https://ucp.dev/specification/
- ✅ **Checkout Sessions**: Full UCP checkout flow with AP2 payment integration
- ✅ **Price Format**: Handles prices in cents (UCP standard)
- ✅ **Independent Systems**: Both backends can run separately
- ✅ **Extensible**: Easy to add more UCP capabilities and extensions

### Chat Backend Features

- 🤖 **AI-powered conversation** with Ollama LLM
- 🔍 **Automatic product search** via UCP product discovery
- 🛒 **Shopping cart management** with session persistence
- 💳 **UCP Checkout integration** with AP2 payment mandates
- 🔐 **WebAuthn passkey authentication** (FIDO2)
- 🔑 **Encrypted card storage** with Fernet encryption
- 🚪 **Logout functionality** with state cleanup
- 💬 **Payment confirmation** shown in chat history
- 🗄️ **Database reset functionality** accessible from chat menu (clears all user data, cards, mandates, and transactions)

### Merchant Backend Features

- 📦 **Full CRUD product management** via REST API
- 🗄️ **SQLite database persistence** for products and logs
- 🔌 **UCP-compliant REST API** with discovery endpoint
- 🛒 **UCP checkout sessions** wrapping AP2 payment processing
- 📊 **Product search and filtering** with UCP format
- 📈 **Merchant dashboard** at app.abhinava.xyz/dashboard
- 📝 **Request/Response logging** for UCP and AP2 calls
- 🔍 **Real-time monitoring** of payment flows
- 🗑️ **Clear logs feature** for dashboard cleanup

### Frontend Features

- ⚛️ **React + TypeScript + Tailwind CSS** modern stack
- 🎨 **Modern, responsive UI** with Lucide icons
- 🔄 **Real-time updates** via Vite HMR
- 📱 **Mobile-friendly design** with responsive layouts
- 🎉 **Payment success confirmations** in chat interface
- 🚪 **Logout button** with confirmation dialog
- 📦 **Product grid display** with add-to-cart functionality

### Security & Payment Features

- 🔐 **WebAuthn/FIDO2 passkeys** - No passwords, biometric auth
- 🔒 **Encrypted card storage** - AES-256 Fernet encryption
- 🎫 **Token-based payments** - 16-digit numeric tokens + cryptograms
- 🔢 **OTP challenges** - Risk-based step-up authentication
- 🔗 **UCP + AP2 integration** - Payments via UCP checkout sessions
- 📋 **Full audit trail** - Request/response logging in dashboard
- 🛡️ **Zero trust architecture** - Credentials and products separated
- 💳 **[OPTIONAL] Mastercard API** - Card tokenization and secure authentication ([docs](MASTERCARD_INTEGRATION.md))

## 🔧 Configuration

### Chat Backend (.env)

```env
OLLAMA_URL=http://192.168.86.41:11434
OLLAMA_MODEL=qwen3:8b
HOST=0.0.0.0
PORT=8452
MERCHANT_BACKEND_URL=http://localhost:8453
```

### Merchant Backend (.env)

```env
DATABASE_URL=sqlite+aiosqlite:///./merchant.db
HOST=0.0.0.0
PORT=8453
MERCHANT_NAME=Enhanced Business Store
MERCHANT_ID=merchant-001
MERCHANT_URL=http://localhost:8453
```

## 📊 Port Allocation

| Service          | Port | Type     | Purpose                                |
| ---------------- | ---- | -------- | -------------------------------------- |
| Chat Frontend    | 8450 | Vite Dev | Customer interface (chat.abhinava.xyz) |
| Merchant Portal  | 8451 | Vite Dev | Admin interface (app.abhinava.xyz)     |
| Chat Backend     | 8452 | FastAPI  | UCP Client + AI Agent                  |
| Merchant Backend | 8453 | FastAPI  | UCP Server + Product DB                |

## 🔐 Production Deployment

For production use:

1. **Set specific CORS origins** in both backends
2. **Use production databases** (PostgreSQL recommended)
3. **Enable HTTPS** with reverse proxy (nginx/Caddy)
4. **Secure API authentication** (JWT, API keys)
5. **Configure Ollama** for production workloads
6. **Monitor UCP endpoints** for performance
7. **Implement rate limiting** on UCP endpoints

## 📝 Logs

View real-time logs (created by `start-split.sh`):

```bash
# Chat Backend
tail -f chat-backend/chat-backend.log

# Merchant Backend
tail -f merchant-backend/merchant-backend.log

# Chat Frontend
tail -f frontend/chat/chat-frontend.log

# Merchant Portal
tail -f frontend/merchant-portal/merchant-portal.log
```

Log locations are displayed when you run `./start-split.sh`.

## 🐛 Troubleshooting

### Port Conflicts

```bash
# Check what's using a port
lsof -i :8450
lsof -i :8453

# Kill process on port
kill -9 $(lsof -ti:8450)
```

### UCP Discovery Fails

```bash
# Verify merchant backend is running
curl http://localhost:8453/health

# Check UCP endpoint
curl http://localhost:8453/.well-known/ucp
```

### Ollama Connection Issues

```bash
# Test Ollama connection
curl http://192.168.86.41:11434/api/tags

# Update OLLAMA_URL in chat-backend/.env
```

## 🎓 Learning Resources

- [UCP Specification](https://github.com/Universal-Commerce-Protocol)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Ollama Documentation](https://ollama.ai/docs)
- [LangChain Documentation](https://python.langchain.com/)

## 📄 License

Apache License 2.0

---

**Built with UCP** - Demonstrating how two independent systems can communicate seamlessly over a universal commerce protocol.
