/**
 * Affinidi TDK Wallet Service
 * Handles DID:web wallet creation and JWT signing (stateless)
 */

import { AuthProvider } from '@affinidi-tdk/auth-provider';
import {
    WalletApi,
    Configuration as WalletsConfiguration,
    CreateWalletV2Input,
    SignCredentialsJwtInputDto,
    WalletDto
} from '@affinidi-tdk/wallets-client';
import {
    DefaultApi as VerificationApi,
    Configuration as VerificationConfiguration,
    VerifyCredentialV2Input
} from '@affinidi-tdk/credential-verification-client';
import { logger } from './logger';
import { AffinidiConfig, WalletData } from './types';

export class AffinidiService {
    private authProvider: AuthProvider;
    private walletApi: WalletApi;
    private verificationApi: VerificationApi;
    private projectId: string;

    constructor(config: AffinidiConfig) {
        this.projectId = config.projectId;

        // Initialize Auth Provider
        this.authProvider = new AuthProvider({
            tokenId: config.tokenId,
            passphrase: config.passphrase,
            privateKey: config.privateKey,
            projectId: config.projectId,
        });

        // Fetch initial project scoped token
        const projectToken = this.authProvider.fetchProjectScopedToken();

        // Configure Wallets API
        const walletsConfig = new WalletsConfiguration({
            apiKey: projectToken,
        });

        // Set up token refresh for wallets
        walletsConfig.accessToken = async () => {
            return this.authProvider.fetchProjectScopedToken();
        };

        this.walletApi = new WalletApi(walletsConfig);

        // Configure Verification API
        const verificationConfig = new VerificationConfiguration({
            apiKey: projectToken,
        });

        // Set up token refresh for verification
        verificationConfig.accessToken = async () => {
            return this.authProvider.fetchProjectScopedToken();
        };

        this.verificationApi = new VerificationApi(verificationConfig);

        logger.info('Initialized AffinidiWalletService');
    }

    /**
     * Create or retrieve DID:web wallet for a domain
     */
    async createOrGetWallet(domain: string): Promise<WalletData> {
        // Build DID from domain
        const encodedDomain = encodeURIComponent(domain);
        const did = `did:web:${encodedDomain}`;
        const didUrl = `https://${domain}`;

        logger.info(`Creating/retrieving wallet for domain: ${domain}, DID: ${did}`);

        try {
            // Check if wallet already exists
            const existingWallet = await this.findWalletByDid(did);

            if (existingWallet) {
                logger.info(`Found existing wallet: ${existingWallet.wallet_id}`);
                return existingWallet;
            }

            // Create new wallet
            logger.info(`Creating new DID:web wallet for ${domain}`);
            const walletData = await this.createWallet(didUrl);

            logger.info(`Successfully created wallet: ${walletData.wallet_id}`);
            return walletData;
        } catch (error) {
            logger.error(`Failed to create/get wallet for ${domain}: ${error}`);
            throw error;
        }
    }

    /**
     * Find existing wallet by DID
     */
    private async findWalletByDid(did: string): Promise<WalletData | null> {
        try {
            const walletsResponse = await this.walletApi.listWallets();

            logger.debug(`Searching for wallet with DID: ${did}`);

            if (walletsResponse.data?.wallets) {
                for (const wallet of walletsResponse.data.wallets) {
                    if (wallet.did === did && wallet.id && wallet.didDocument) {
                        const signingKeyId = this.extractSigningKeyId(wallet.didDocument);

                        return {
                            wallet_id: wallet.id,
                            did: wallet.did,
                            did_document: wallet.didDocument,
                            signing_key_id: signingKeyId,
                        };
                    }
                }
            }

            return null;
        } catch (error: any) {
            if (error?.status === 404) {
                return null;
            }
            throw error;
        }
    }

    /**
     * Create a new DID:web wallet
     */
    private async createWallet(didUrl: string): Promise<WalletData> {
        try {
            const createWalletInput: CreateWalletV2Input = {
                didMethod: 'web',
                didWebUrl: didUrl,
                name: 'DID:web Wallet',
                description: `DID:web wallet for ${didUrl}`,
            };

            const walletResponse = await this.walletApi.createWalletV2(createWalletInput);
            const wallet = walletResponse.data?.wallet;

            if (!wallet || !wallet.id || !wallet.didDocument) {
                throw new Error('Invalid wallet creation response');
            }

            // Get full wallet details
            const walletDetails = await this.walletApi.getWallet(wallet.id);

            const signingKeyId = this.extractSigningKeyId(wallet.didDocument);

            return {
                wallet_id: wallet.id,
                did: wallet.did!,
                did_document: wallet.didDocument,
                signing_key_id: signingKeyId,
            };
        } catch (error) {
            logger.error(`Failed to create wallet: ${error}`);
            throw error;
        }
    }

    /**
     * Sign a verifiable credential with the wallet's private key
     */
    async signCredential(
        domain: string,
        unsignedCredential: Record<string, any>
    ): Promise<string> {
        try {
            // Get or create wallet
            const walletData = await this.createOrGetWallet(domain);

            // Sign credential using sign_credentials_jwt
            const signInput: SignCredentialsJwtInputDto = {
                unsignedCredential: unsignedCredential,
                signatureScheme: 'ecdsa_secp256k1_sha256',
            };

            const signResponse = await this.walletApi.signCredentialsJwt(walletData.wallet_id
                , signInput);

            logger.info(`Signed credential for domain ${domain}`);
            return signResponse.data?.credential;
        } catch (error) {
            logger.error(`Failed to sign credential for ${domain}: ${error}`);
            throw error;
        }
    }

    /**
     * Verify a verifiable credential JWT
     */
    async verifyCredential(jwtVc: string): Promise<{
        valid: boolean;
        verified: boolean;
        error?: string;
    }> {
        try {
            // Validate JWT format
            const parts = jwtVc.split('.');
            if (parts.length !== 3) {
                return {
                    valid: false,
                    verified: false,
                    error: 'Invalid JWT format - must have 3 parts',
                };
            }

            // Create verification request
            const verifyInput: VerifyCredentialV2Input = {
                jwtVcs: [jwtVc],
            };

            // Call verification API
            const verificationResponse = await this.verificationApi.verifyCredentialsV2(verifyInput);

            // Log only the relevant data properties (avoid circular references)
            logger.info(`Verification result - Valid: ${verificationResponse.data.isValid}, Errors: ${verificationResponse.data.errors?.join(', ') || 'none'}`);

            return {
                valid: verificationResponse.data.isValid,
                verified: true,
                error: verificationResponse.data.errors?.join(', ') || undefined,
            };
        } catch (error) {
            logger.error(`Affinidi credential verification failed: ${error}`);
            return {
                valid: false,
                verified: false,
                error: `Verification failed: ${error}`,
            };
        }
    }

    /**
     * Extract the first signing key ID from DID document
     */
    private extractSigningKeyId(didDocument: any): string {
        // Look for assertionMethod or verificationMethod
        if (didDocument.assertionMethod && didDocument.assertionMethod.length > 0) {
            const firstKey = didDocument.assertionMethod[0];
            if (typeof firstKey === 'string') {
                return firstKey;
            } else if (typeof firstKey === 'object' && firstKey.id) {
                return firstKey.id;
            }
        }

        if (didDocument.verificationMethod && didDocument.verificationMethod.length > 0) {
            return didDocument.verificationMethod[0].id;
        }

        throw new Error('No signing key found in DID document');
    }
}
