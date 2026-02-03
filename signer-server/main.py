"""
Signer Server - Affinidi TDK Wallet Management & JWT Signing
Isolates pydantic v1 dependencies from merchant backend
"""

import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from affinidi_service import AffinidiWalletService

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global Affinidi service (initialized at startup)
affinidi_service: Optional[AffinidiWalletService] = None


# ============================================================================
# Pydantic Models
# ============================================================================

class CreateWalletRequest(BaseModel):
    domain: str


class CreateWalletResponse(BaseModel):
    did: str
    did_document: Dict[str, Any]
    wallet_id: str
    signing_key_id: str


class SignCredentialRequest(BaseModel):
    domain: str
    unsigned_credential: Dict[str, Any]


class SignCredentialResponse(BaseModel):
    signed_credential: str


class VerifyCredentialRequest(BaseModel):
    jwt_vc: str


class VerifyCredentialResponse(BaseModel):
    valid: bool
    verified: bool
    payload: Optional[Dict[str, Any]] = None
    header: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    global affinidi_service

    logger.info("Signer Server starting up...")

    # Load Affinidi credentials and initialize service
    project_id = os.getenv("PROJECT_ID")
    token_id = os.getenv("TOKEN_ID")
    passphrase = os.getenv("PASSPHRASE")
    private_key = os.getenv("PRIVATE_KEY")

    if not all([project_id, token_id, passphrase, private_key]):
        logger.error("Missing Affinidi credentials in .env file")
        raise ValueError(
            "Affinidi credentials not configured. Set PROJECT_ID, TOKEN_ID, PASSPHRASE, PRIVATE_KEY in .env")

    affinidi_service = AffinidiWalletService(
        project_id=project_id,
        token_id=token_id,
        passphrase=passphrase,
        private_key=private_key
    )

    logger.info("Affinidi Wallet Service initialized successfully")

    yield

    # Cleanup
    logger.info("Signer Server shutting down...")
    if affinidi_service:
        try:
            affinidi_service.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up Affinidi service: {e}")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Signer Server API",
    description="Affinidi TDK Wallet Management & JWT Signing Service",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Signer Server",
        "version": "1.0.0",
        "description": "Affinidi TDK Wallet Management & JWT Signing Service",
        "endpoints": {
            "did_web_generate": "POST /api/did-web-generate",
            "sign_credential": "POST /api/sign-credential",
            "verify_credential": "POST /api/verify-credential",
            "health": "GET /health"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/did-web-generate", response_model=CreateWalletResponse)
async def generate_did_web(request: CreateWalletRequest):
    """
    Generate or retrieve DID:web wallet for a domain.

    Args:
        request: Contains domain name (e.g., "merchant.example.com" or "localhost:8453")

    Returns:
        Wallet information including DID, DID document, wallet ID, and signing key ID
    """
    try:
        wallet_data = affinidi_service.create_or_get_wallet(request.domain)

        return CreateWalletResponse(
            did=wallet_data['did'],
            did_document=wallet_data['did_document'],
            wallet_id=wallet_data['wallet_id'],
            signing_key_id=wallet_data['signing_key_id']
        )

    except Exception as e:
        logger.error(
            f"Failed to generate DID:web wallet for domain {request.domain}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate DID:web wallet: {str(e)}"
        )


@app.post("/api/sign-credential", response_model=SignCredentialResponse)
async def sign_credential(request: SignCredentialRequest):
    """
    Sign a verifiable credential with the wallet's private key.
    Uses sign_credentials_jwt TDK method.

    Args:
        request: Contains domain and unsigned_credential dict

    Returns:
        Signed credential JWT string
    """
    try:
        signed_credential = affinidi_service.sign_credential(
            domain=request.domain,
            unsigned_credential=request.unsigned_credential
        )

        return SignCredentialResponse(signed_credential=signed_credential)

    except Exception as e:
        logger.error(
            f"Failed to sign credential for domain {request.domain}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sign credential: {str(e)}"
        )


@app.post("/api/verify-credential", response_model=VerifyCredentialResponse)
async def verify_credential(request: VerifyCredentialRequest):
    """
    Verify a verifiable credential signature.
    Uses verify_credentials_v2 TDK method with jwt_vcs parameter.

    Args:
        request: Contains JWT VC string

    Returns:
        Verification result with payload and header if valid
    """
    try:
        result = await affinidi_service.verify_credential(
            jwt_vc=request.jwt_vc,
        )

        return VerifyCredentialResponse(**result)

    except Exception as e:
        logger.error(f"Failed to verify credential: {e}")
        return VerifyCredentialResponse(
            valid=False,
            verified=False,
            error=str(e)
        )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8454"))

    logger.info(f"Starting Signer Server on port {port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
