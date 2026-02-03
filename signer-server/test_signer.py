#!/usr/bin/env python3
"""
Test script for Signer Server endpoints
Tests DID generation, JWT signing, and JWT verification
"""

import httpx
import json
import time
from datetime import datetime, timedelta

SIGNER_URL = "http://localhost:8454"


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(label, data):
    """Print formatted result."""
    print(f"\n{label}:")
    print(json.dumps(data, indent=2))


async def test_did_generation(domain):
    """Test DID:web generation endpoint."""
    print_section("Test 1: DID:web Generation")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SIGNER_URL}/api/did-web-generate",
            json={"domain": domain},
            timeout=30.0
        )

        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print_result("DID Generation Result", {
                "did": result["did"],
                "wallet_id": result["wallet_id"],
                "signing_key_id": result["signing_key_id"],
                "did_document_keys": list(result["did_document"].keys())
            })
            return result
        else:
            print(f"Error: {response.text}")
            return None


async def test_credential_signing(did_info, domain):
    """Test Credential signing endpoint."""
    print_section("Test 2: Credential Signing")

    cart_id = "CART-12345"
    # Build unsigned credential
    unsigned_credential = {
        "@context": ["https://www.w3.org/2018/credentials/v1", "https://ap2-protocol.org/mandates/v1"],
        "type": ["VerifiableCredential", "CartMandate"],
        "id": f"urn:uuid:mandate-{cart_id}",
        "issuanceDate": datetime.utcnow().isoformat() + "Z",
        "credentialSubject": {
            'id': 'did:example:holder123',
            "cart_id": cart_id,
            "merchant_name": "Test Merchant Store",
            "contents": "some content describing the cart mandate"
        }
    }

    print(f"\nUnsigned Credential:")
    print(json.dumps(unsigned_credential, indent=2))

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SIGNER_URL}/api/sign-credential",
            json={
                "domain": domain,
                "unsigned_credential": unsigned_credential
            },
            timeout=30.0
        )

        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            signed_credential = result["signed_credential"]

            # Show credential JWT parts
            parts = signed_credential.split('.')
            print_result("Credential Signing Result", {
                "signed_credential_length": len(signed_credential),
                "header_length": len(parts[0]),
                "payload_length": len(parts[1]),
                "signature_length": len(parts[2]),
                "full_credential": signed_credential
            })

            return signed_credential
        else:
            print(f"Error: {response.text}")
            return None


async def test_credential_verification(jwt_vc):
    """Test Credential verification endpoint."""
    print_section("Test 3: Credential Verification")

    print(f"\nVerifying Credential: {jwt_vc[:50]}...")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SIGNER_URL}/api/verify-credential",
            json={
                "jwt_vc": jwt_vc
            },
            timeout=30.0
        )

        print(f"\nStatus Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print_result("Credential Verification Result", {
                "valid": result.get("valid"),
                "verified": result.get("verified"),
                "error": result.get("error")
            })

            return result
        else:
            print(f"Error: {response.text}")
            return None


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  Signer Server Test Suite")
    print("  Testing: http://localhost:8454")
    print("=" * 60)

    try:

        domain = "marmot-suited-muskrat.ngrok-free.app"
        # # Test 1: DID Generation
        did_info = await test_did_generation(domain)
        if not did_info:
            print("\n❌ DID generation failed, stopping tests")
            return

        print("\n✅ DID generation successful")
        time.sleep(1)

        # Test 2: Credential Signing
        signed_credential = await test_credential_signing(did_info, domain)
        time.sleep(1)

        # Test 3: Credential Verification (valid credential)
        verification_result = await test_credential_verification(signed_credential)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
