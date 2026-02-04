/**
 * Type definitions for Trusted Service
 */

export interface CreateWalletRequest {
    domain: string;
}

export interface CreateWalletResponse {
    did: string;
    did_document: Record<string, any>;
    wallet_id: string;
    signing_key_id: string;
}

export interface SignCredentialRequest {
    domain: string;
    unsigned_credential: Record<string, any>;
}

export interface SignCredentialResponse {
    signed_credential: string;
}

export interface VerifyCredentialRequest {
    jwt_vc: string;
}

export interface VerifyCredentialResponse {
    valid: boolean;
    verified: boolean;
    payload?: Record<string, any>;
    header?: Record<string, any>;
    error?: string;
}

export interface WalletData {
    wallet_id: string;
    did: string;
    did_document: object;
    signing_key_id: string;
}

export interface AffinidiConfig {
    projectId: string;
    tokenId: string;
    passphrase: string;
    privateKey: string;
}
