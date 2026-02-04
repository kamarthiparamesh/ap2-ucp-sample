## Pre-Requisite

Before running the signer service, you need to obtain Affinidi credentials from the Affinidi Portal.

> [!IMPORTANT]
> Mandatory steps before proceeding to next steps.

### Create Personal Access Token (PAT)

Personal Access Token (PAT) is like a machine user that acts on your behalf to the Affinidi services. You can use the PAT to authenticate to the Affinidi services and automate specific tasks within your application. A Personal Access Token (PAT) lives outside of Projects, meaning PAT can access multiple projects once granted by the user.

- More details: [Personal Access Token](https://docs.affinidi.com/dev-tools/affinidi-cli/manage-token/#how-does-pat-authentication-works)
- PAT is needed for `Affinidi TDK Auth provider`.

You can refer the [Affinidi Documentation](https://docs.affinidi.com/dev-tools/affinidi-cli/manage-token/#affinidi-token-create-token) for creating pesronal access token from CLI.

**Steps to Create PAT(Personal Access Token):**

1. **Log in to Affinidi CLI:**

   ```sh
   affinidi start
   ```

2. **Create a token:**

   ```sh
   affinidi token create-token
   ```

   Follow the instruction

   ```
    ? Enter the value for name workshopPAT
    ? Generate a new keypair for the token? yes
    ? Enter a passphrase to encrypt the private key. Leave it empty for no encryption ******
    ? Add token to active project and grant permissions? yes
    ? Enter the allowed resources, separated by spaces. Use * to allow access to all project resources *
    ? Enter the allowed actions, separated by spaces. Use * to allow all actions *
   ```

   **Sample response:**

   ```json
    Creating Personal Access Token... Created successfully!
    Adding token to active project... Added successfully!
    Granting permissions to token... Granted successfully!
    {
      "id": "**********",
      "ari": "ari:iam:::token/**********",
      "ownerAri": "ari:iam:::user/**********",
      "name": "workshopPAT",
      "scopes": [
        "openid",
        "offline_access"
      ],
      "authenticationMethod": {
        "type": "PRIVATE_KEY",
        "signingAlgorithm": "RS256",
        "publicKeyInfo": {
          "jwks": {
            "keys": [
              {
                "use": "sig",
                "kty": "RSA",
                "kid": "**********",
                "alg": "RS256",
                "n": "**********",
                "e": "AQAB"
              }
            ]
          }
        }
      }
    }

    Use the projectId, tokenId, privateKey, and passphrase (if provided) to use this token with Affinidi TDK
    {
      "tokenId": "*******",
      "projectId": "*******",
      "privateKey": "*******",
      "passphrase": "******"
    }
    ›   Warning:
    ›   Please save the privateKey and passphrase (if provided) somewhere safe. You will not be able to view them again.
    ›

   ```

   For more details on the command run the below command

   ```sh
   affinidi token create-token --help
   ```

## ⚙️ Environment Variable Setup

update your `.env` file (or relevant environment configuration) with the following variables:

```env
PROJECT_ID=your_affinidi_project_id
TOKEN_ID=your_token_id
PASSPHRASE=your_passphrase
PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
PORT=8454
```

## 🏗️ Architecture Overview

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

📋 Credential Flow:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
① Merchant Startup  → Call Signer: DID Generation → Store DID doc (.well-known)
② Checkout Created  → Call Signer: Sign Credential → Merchant's DID:web signature
③ Payment Process   → Call Signer: Verify Credential → Cryptographic verification
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 🔐 Signer Service Details

### Three Core Endpoints

#### 1️⃣ DID Generation (`POST /api/did-web-generate`)

**Purpose**: Creates or retrieves a `did:web` wallet for a domain

**Request**:

```json
{
  "domain": "localhost:8453"
}
```

**Response**:

```json
{
  "did": "did:web:localhost%3A8453",
  "did_document": { ... },
  "wallet_id": "...",
  "signing_key_id": "..."
}
```

**Integration**:

- Called during **Merchant Backend startup**
- DID document stored to serve `/.well-known/did.json`
- Wallet uses **Affinidi TDK** for key pair management

---

#### 2️⃣ Sign Credential (`POST /api/sign-credential`)

**Purpose**: Signs JWT Verifiable Credentials using the wallet's private key

**Request**:

```json
{
  "domain": "localhost:8453",
  "unsigned_credential": {
    "@context": [...],
    "type": ["VerifiableCredential", "CartMandateCredential"],
    "credentialSubject": {
      "cartHash": "abc123...",
      "totalAmount": 150.00,
      ...
    }
  }
}
```

**Response**:

```json
{
  "signed_credential": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImRpZDp3ZWI6bG9jYWxob3N0..."
}
```

**Integration**:

- Called during **Checkout Session Update** (when payment mandate is added)
- Creates **Cart Mandate VC** signed by merchant's DID:web
- Signature proves merchant commits to cart contents and pricing

---

#### 3️⃣ Verify Credential (`POST /api/verify-credential`)

**Purpose**: Verifies JWT-VC signature by resolving issuer's DID:web

**Request**:

```json
{
  "jwt_vc": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImRpZDp3ZWI6bG9jYWxob3N0..."
}
```

**Response**:

```json
{
  "valid": true,
  "verified": true,
  "errors": []
}
```

**Integration**:

- Called during **Payment Processing** (before completing payment)
- Verifies **Cart Mandate VC** hasn't been tampered with
- Resolves issuer DID and validates signature cryptographically

---

## 🔄 Merchant Backend Integration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Merchant Backend Lifecycle                                     │
└─────────────────────────────────────────────────────────────────┘

1. STARTUP (app lifespan)
   ├─ Initialize SignerClient(url="http://localhost:8454")
   ├─ Call: POST /api/did-web-generate
   │  └─ Domain: "localhost:8453" (or production domain)
   ├─ Receive: DID, DID Document, Wallet ID
   └─ Store DID document → serve at /.well-known/did.json

2. CHECKOUT SESSION UPDATE (add payment mandate)
   ├─ Build unsigned Cart Mandate credential
   │  └─ Contains: cartHash, totalAmount, currency, mandateId
   ├─ Call: POST /api/sign-credential
   │  └─ Domain + unsigned_credential
   ├─ Receive: Signed JWT-VC
   └─ Store merchant_authorization in checkout session

3. PAYMENT PROCESSING (complete checkout)
   ├─ Extract merchant_authorization from payment mandate
   ├─ Call: POST /api/verify-credential
   │  └─ JWT-VC from merchant_authorization
   ├─ Receive: Verification result (valid/verified)
   ├─ If TESTFAIL promocode → tampered JWT → verification FAILS
   └─ Proceed with payment ONLY if verification succeeds
```

---

## 🛡️ Security Features

### DID:web Trust Model

- **Decentralized Identifiers**: No central authority required
- **Web-based Resolution**: DID document served via HTTPS
- **Public Key Distribution**: Verification keys published in DID document

### Cryptographic Signing

- **Affinidi TDK**: Enterprise-grade wallet management
- **ES256 Algorithm**: Elliptic Curve Digital Signature (ECDSA with P-256)
- **Non-repudiation**: Merchant cannot deny signing cart mandate

### Tamper Detection

- **Cart Hash**: SHA-256 hash of cart contents
- **Signature Verification**: Any modification breaks signature
- **Demo Feature**: TESTFAIL promocode simulates tampering for testing

---

## 🚀 Running the Signer Service

```bash
cd signer-server
./start.sh
```

**Health Check**:

```bash
curl http://localhost:8454/health
```

**Expected Response**:

```json
{
  "status": "healthy"
}
```

---

## 📦 Dependencies

- **affinidi-tdk-wallets-client**: DID:web wallet creation and JWT signing
- **affinidi-tdk-credential-verification-client**: JWT-VC verification
- **affinidi-tdk-auth-provider**: Project-scoped authentication

---

## 🧪 Testing Flow

1. **Start Signer Service**: `python main.py` (Port 8454)
2. **Start Merchant Backend**: Will auto-create DID:web wallet
3. **Create Checkout**: Cart mandate gets signed
4. **Normal Payment**: Verification succeeds → payment processes
5. **Tamper Test**: Use promocode `TESTFAIL` → verification fails → payment rejected

---

## 📖 Related Documentation

- [UCP Knowledge Base](../UCP-KNOWLEDGE-BASE.md)
- [Mastercard Integration](../MASTERCARD_INTEGRATION.md)
- [Affinidi TDK Documentation](https://docs.affinidi.com)
