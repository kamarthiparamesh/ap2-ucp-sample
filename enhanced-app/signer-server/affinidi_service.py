"""
Affinidi TDK Wallet Service
Handles DID:web wallet creation and JWT signing (stateless)
"""

import logging
from typing import Dict, Any, Optional
from urllib.parse import quote
import base64
import json
import hashlib

import affinidi_tdk_wallets_client
from affinidi_tdk_wallets_client import Configuration, ApiClient
from affinidi_tdk_wallets_client.api.wallet_api import WalletApi
from affinidi_tdk_wallets_client.models.create_wallet_v2_input import CreateWalletV2Input
from affinidi_tdk_wallets_client.models.sign_credentials_jwt_input_dto import SignCredentialsJwtInputDto
from affinidi_tdk_wallets_client.rest import ApiException
import affinidi_tdk_auth_provider
import affinidi_tdk_credential_verification_client
from affinidi_tdk_credential_verification_client import Configuration as VerificationConfiguration
from affinidi_tdk_credential_verification_client import ApiClient as VerificationApiClient
from affinidi_tdk_credential_verification_client.api.default_api import DefaultApi
from affinidi_tdk_credential_verification_client.models.verify_credential_v2_input import VerifyCredentialV2Input

logger = logging.getLogger(__name__)


class AffinidiWalletService:
    """
    Stateless service for managing Affinidi DID:web wallets and JWT signing.
    Can handle multiple domains.
    """

    def __init__(
        self,
        project_id: str,
        token_id: str,
        passphrase: str,
        private_key: str
    ):
        """
        Initialize Affinidi Wallet Service.

        Args:
            project_id: Affinidi project ID
            token_id: Authentication token ID
            passphrase: Key passphrase
            private_key: Private key for authentication (PEM format)
        """
        self.project_id = project_id

        # Configure Affinidi TDK client
        configuration = Configuration()

        # Set up auth provider
        auth_stats = {
            "tokenId": token_id,
            "passphrase": passphrase,
            "privateKey": private_key,
            "projectId": project_id,
        }

        self.auth_provider = affinidi_tdk_auth_provider.AuthProvider(
            auth_stats)

        # Fetch initial project scoped token
        project_token = self.auth_provider.fetch_project_scoped_token()
        configuration.api_key['ProjectTokenAuth'] = project_token

        # Set up auto-refresh hook
        def refresh_token(api_client):
            token = self.auth_provider.fetch_project_scoped_token()
            configuration.api_key['ProjectTokenAuth'] = token
            return token

        configuration.refresh_api_key_hook = refresh_token

        self.api_client = ApiClient(configuration)
        self.wallet_api = WalletApi(self.api_client)

        # Set up credential verification client
        verification_configuration = VerificationConfiguration()
        verification_configuration.api_key['ProjectTokenAuth'] = project_token
        verification_configuration.refresh_api_key_hook = refresh_token
        self.verification_api_client = VerificationApiClient(
            verification_configuration)
        self.verification_api = DefaultApi(self.verification_api_client)

        logger.info("Initialized AffinidiWalletService")

    def create_or_get_wallet(self, domain: str) -> Dict[str, Any]:
        """
        Create or retrieve DID:web wallet for a domain.

        Args:
            domain: Domain name (e.g., "merchant.example.com" or "localhost:8453")

        Returns:
            Wallet information including DID, DID document, wallet ID, and signing_key_id
        """
        # Build DID from domain
        encoded_domain = quote(domain, safe='')
        did = f"did:web:{encoded_domain}"
        did_url = f"https://{domain}"

        logger.info(
            f"Creating/retrieving wallet for domain: {domain}, DID: {did}")

        try:
            # Check if wallet already exists
            existing_wallet = self._find_wallet_by_did(did)

            if existing_wallet:
                logger.info(
                    f"Found existing wallet: {existing_wallet['wallet_id']}")
                return existing_wallet

            # Create new wallet
            logger.info(f"Creating new DID:web wallet for {domain}")
            wallet_data = self._create_wallet(did_url)

            logger.info(
                f"Successfully created wallet: {wallet_data['wallet_id']}")
            return wallet_data

        except Exception as e:
            logger.error(f"Failed to create/get wallet for {domain}: {e}")
            raise

    def _find_wallet_by_did(self, did: str) -> Optional[Dict[str, Any]]:
        """
        Find existing wallet by DID.

        Args:
            did: DID identifier

        Returns:
            Wallet data or None
        """
        try:
            wallets_response = self.wallet_api.list_wallets()

            logger.debug(f"Searching for wallet with DID: {did}")

            if wallets_response.wallets:
                for wallet in wallets_response.wallets:
                    if wallet.did == did:
                        wallet_details = self.wallet_api.get_wallet(wallet.id)
                        signing_key_id = self._extract_signing_key_id(
                            wallet_details.did_document)

                        return {
                            'wallet_id': wallet.id,
                            'did': wallet.did,
                            'did_document': wallet_details.did_document,
                            'signing_key_id': signing_key_id
                        }

            return None

        except ApiException as e:
            if e.status == 404:
                return None
            raise

    def _create_wallet(self, did_url: str) -> Dict[str, Any]:
        """
        Create a new DID:web wallet.

        Args:
            did_url: DID URL (e.g., "https://merchant.example.com")

        Returns:
            Created wallet data
        """
        try:
            create_wallet_json = {
                "didMethod": "web",
                "didWebUrl": did_url,
                "name": "DID:web Wallet",
                "description": f"DID:web wallet for {did_url}"
            }

            create_input = CreateWalletV2Input.from_dict(create_wallet_json)
            wallet_response = self.wallet_api.create_wallet_v2(
                create_wallet_v2_input=create_input)

            # Get full wallet details
            wallet_details = self.wallet_api.get_wallet(
                wallet_response.wallet.id)
            signing_key_id = self._extract_signing_key_id(
                wallet_details.did_document)

            return {
                'wallet_id': wallet_response.wallet.id,
                'did': wallet_response.wallet.did,
                'did_document': wallet_details.did_document,
                'signing_key_id': signing_key_id
            }

        except ApiException as e:
            logger.error(f"Failed to create wallet: {e}")
            raise

    def sign_credential(
        self,
        domain: str,
        unsigned_credential: Dict[str, Any]
    ) -> str:
        """
        Sign a verifiable credential with the wallet's private key using sign_credentials_jwt.

        Args:
            domain: Domain name
            unsigned_credential: Unsigned verifiable credential (should contain @context, type, credentialSubject, etc.)

        Returns:
            Signed credential JWT string
        """
        try:
            # Get or create wallet
            wallet_data = self.create_or_get_wallet(domain)

            # Sign credential using sign_credentials_jwt
            sign_credential_input = SignCredentialsJwtInputDto(
                unsigned_credential=unsigned_credential,
                signature_scheme="ecdsa_secp256k1_sha256"
            )

            sign_response = self.wallet_api.sign_credentials_jwt(
                wallet_id=wallet_data['wallet_id'],
                sign_credentials_jwt_input_dto=sign_credential_input
            )

            logger.info(f"Signed credential for domain {domain}")
            return sign_response.credential

        except Exception as e:
            logger.error(f"Failed to sign credential for {domain}: {e}")
            raise

    def _extract_signing_key_id(self, did_document: Dict[str, Any]) -> str:
        """
        Extract the first signing key ID from DID document.

        Args:
            did_document: DID document

        Returns:
            Key ID (kid) for signing
        """
        # Look for assertionMethod or verificationMethod
        if 'assertionMethod' in did_document and did_document['assertionMethod']:
            first_key = did_document['assertionMethod'][0]
            if isinstance(first_key, str):
                return first_key
            elif isinstance(first_key, dict) and 'id' in first_key:
                return first_key['id']

        if 'verificationMethod' in did_document and did_document['verificationMethod']:
            return did_document['verificationMethod'][0]['id']

        raise ValueError("No signing key found in DID document")

    async def verify_credential(
        self,
        jwt_vc: str,
    ) -> Dict[str, Any]:
        """
        Verify a verifiable credential JWT using Affinidi verify_credentials_v2 endpoint.

        Args:
            jwt_vc: Verifiable credential JWT string to verify

        Returns:
            Dict with verification result
        """

        # Use Affinidi verify_credentials_v2 endpoint
        try:
            # Decode header and payload for response
            parts = jwt_vc.split('.')
            if len(parts) != 3:
                return {
                    "valid": False,
                    "verified": False,
                    "error": "Invalid JWT format - must have 3 parts"
                }

            # Create verification request with jwt_vcs parameter
            verify_input = VerifyCredentialV2Input(
                jwt_vcs=[jwt_vc]
            )

            # Call verification API
            verification_response = self.verification_api.verify_credentials_v2(
                verify_credential_v2_input=verify_input
            )

            print('verification_response:', verification_response.to_str())

            return {
                "valid": verification_response.is_valid,
                "verified": True,
                "error": ', '.join(verification_response.errors) if verification_response.errors else None
            }

        except Exception as e:
            logger.error(f"Affinidi credential verification failed: {e}")
            return {
                "valid": False,
                "verified": False,
                "error": f"Verification failed: {str(e)}"
            }

    def cleanup(self):
        """Cleanup resources."""
        if self.api_client:
            self.api_client.close()
        if self.verification_api_client:
            self.verification_api_client.close()
