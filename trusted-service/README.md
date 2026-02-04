# Trusted Service

TypeScript-based Affinidi TDK Wallet Management & JWT Signing Service

## Overview

This is a TypeScript port of the `signer-server` (Python version), providing the same functionality using the Affinidi TDK TypeScript/JavaScript SDK.

**Key Features:**

- DID:web wallet creation and management
- Verifiable Credential signing (JWT format)
- Credential verification

## Pre-Requisites

### Create Personal Access Token (PAT)

Before running the trusted service, you need to obtain Affinidi credentials from the Affinidi Portal.

> [!IMPORTANT]
> Mandatory steps before proceeding to next steps.

Personal Access Token (PAT) is like a machine user that acts on your behalf to the Affinidi services. You can use the PAT to authenticate to the Affinidi services and automate specific tasks within your application.

- More details: [Personal Access Token](https://docs.affinidi.com/dev-tools/affinidi-cli/manage-token/#how-does-pat-authentication-works)
- PAT is needed for `Affinidi TDK Auth provider`.

**Steps to Create PAT (Personal Access Token):**

1. **Log in to Affinidi CLI:**

   ```sh
   affinidi start
   ```

2. **Create a token:**

   ```sh
   affinidi token create-token
   ```

   Follow the instructions:

   ```
   ? Enter the value for name workshopPAT
   ? Generate a new keypair for the token? yes
   ? Enter a passphrase to encrypt the private key. Leave it empty for no encryption ******
   ? Add token to active project and grant permissions? yes
   ? Enter the allowed resources, separated by spaces. Use * to allow access to all project resources *
   ? Enter the allowed actions, separated by spaces. Use * to allow all actions *
   ```

   Save the `tokenId`, `projectId`, `privateKey`, and `passphrase` from the response.

## Environment Variables

Create a `.env` file in the `trusted-service` directory:

```env
# Affinidi TDK Credentials
PROJECT_ID=your-project-id
TOKEN_ID=your-token-id
PASSPHRASE=your-passphrase
PRIVATE_KEY=your-private-key

# Server Configuration
PORT=8454
NODE_ENV=development
```

## Installation

```bash
npm install
```

## Running the Service

### Development Mode (with hot reload)

```bash
npm run dev
```

### Production Mode

```bash
# Build TypeScript
npm run build

# Start server
npm start
```

### Using the startup script

```bash
chmod +x start.sh
./start.sh
```

## API Endpoints

### 1. Root Endpoint

- **URL:** `GET /`
- **Description:** Service information

### 2. Health Check

- **URL:** `GET /health`
- **Response:** `{ "status": "healthy" }`

### 3. Generate DID:web Wallet

- **URL:** `POST /api/did-web-generate`
- **Request Body:**
  ```json
  {
    "domain": "merchant.example.com"
  }
  ```
- **Response:**
  ```json
  {
    "did": "did:web:merchant.example.com",
    "did_document": { ... },
    "wallet_id": "...",
    "signing_key_id": "..."
  }
  ```

### 4. Sign Credential

- **URL:** `POST /api/sign-credential`
- **Request Body:**
  ```json
  {
    "domain": "merchant.example.com",
    "unsigned_credential": {
      "@context": ["https://www.w3.org/2018/credentials/v1"],
      "type": ["VerifiableCredential"],
      "issuer": "did:web:merchant.example.com",
      "credentialSubject": { ... }
    }
  }
  ```
- **Response:**
  ```json
  {
    "signed_credential": "eyJhbGciOi..."
  }
  ```

### 5. Verify Credential

- **URL:** `POST /api/verify-credential`
- **Request Body:**
  ```json
  {
    "jwt_vc": "eyJhbGciOi..."
  }
  ```
- **Response:**
  ```json
  {
    "valid": true,
    "verified": true,
    "error": null
  }
  ```

## Testing

Run the test script to verify the service functionality:

```bash
npm test
```

This will:

1. Create/retrieve a DID:web wallet
2. Sign a test credential
3. Verify the signed credential

## Architecture

```
trusted-service/
├── src/
│   ├── server.ts              # Express server & API endpoints
│   ├── affinidi-service.ts    # Affinidi TDK wallet operations
│   ├── types.ts               # TypeScript type definitions
│   ├── logger.ts              # Winston logger configuration
│   └── test-signer.ts         # Test script
├── package.json
├── tsconfig.json
├── .env
└── README.md
```

## Key Dependencies

- **@affinidi-tdk/auth-provider** - Authentication with Affinidi services
- **@affinidi-tdk/wallets-client** - Wallet management API
- **@affinidi-tdk/credential-verification-client** - Credential verification API
- **express** - HTTP server framework
- **winston** - Logging
- **typescript** - Type safety

## Differences from Python Version

1. **Language:** TypeScript instead of Python
2. **HTTP Framework:** Express.js instead of FastAPI
3. **SDK:** Affinidi TDK TypeScript instead of Python
4. **Type Safety:** Full TypeScript type definitions
5. **API Compatibility:** Same endpoint structure and response formats

## Port Configuration

Default port: `8454` (same as Python version)

Can be changed via `PORT` environment variable.

## Logging

Uses Winston for structured logging with timestamps and log levels.

Configure log level via `LOG_LEVEL` environment variable (default: `info`).

## License

ISC
