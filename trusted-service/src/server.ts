/**
 * Trusted Service - Affinidi TDK Wallet Management & JWT Signing
 * TypeScript implementation using Express.js
 */

import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { logger } from './logger';
import { AffinidiService } from './affinidi-service';
import {
    CreateWalletRequest,
    CreateWalletResponse,
    SignCredentialRequest,
    SignCredentialResponse,
    VerifyCredentialRequest,
    VerifyCredentialResponse,
} from './types';
import { log } from 'console';

// Load environment variables
dotenv.config();

// Global Affinidi service
let affinidiService: AffinidiService;

// Initialize Express app
const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Request logging middleware
app.use((req: Request, res: Response, next: NextFunction) => {
    logger.info(`${req.method} ${req.path}`);
    next();
});

// ============================================================================
// API Endpoints
// ============================================================================

app.get('/', (req: Request, res: Response) => {
    res.json({
        service: 'Trusted Service',
        version: '1.0.0',
        description: 'Affinidi TDK Wallet Management & JWT Signing Service (TypeScript)',
        endpoints: {
            did_web_generate: 'POST /api/did-web-generate',
            sign_credential: 'POST /api/sign-credential',
            verify_credential: 'POST /api/verify-credential',
            health: 'GET /health',
        },
    });
});

app.get('/health', (req: Request, res: Response) => {
    res.json({ status: 'healthy' });
});

app.post('/api/did-web-generate', async (req: Request, res: Response) => {
    try {
        const { domain } = req.body as CreateWalletRequest;

        if (!domain) {
            return res.status(400).json({ error: 'domain is required' });
        }

        const walletData = await affinidiService.createOrGetWallet(domain);

        const response: CreateWalletResponse = {
            did: walletData.did,
            did_document: walletData.did_document,
            wallet_id: walletData.wallet_id,
            signing_key_id: walletData.signing_key_id,
        };

        res.json(response);
    } catch (error: any) {
        logger.error(`Failed to generate DID:web wallet: ${error}`);
        res.status(500).json({
            error: 'Failed to generate DID:web wallet',
            detail: error.message,
        });
    }
});

app.post('/api/sign-credential', async (req: Request, res: Response) => {
    try {
        const { domain, unsigned_credential } = req.body as SignCredentialRequest;

        if (!domain || !unsigned_credential) {
            return res.status(400).json({ error: 'domain and unsigned_credential are required' });
        }

        const signedCredential = await affinidiService.signCredential(
            domain,
            unsigned_credential
        );

        const response: SignCredentialResponse = {
            signed_credential: signedCredential,
        };

        res.json(response);
    } catch (error: any) {
        logger.error(`Failed to sign credential: ${error}`);
        res.status(500).json({
            error: 'Failed to sign credential',
            detail: error.message,
        });
    }
});

app.post('/api/verify-credential', async (req: Request, res: Response) => {
    try {
        const { jwt_vc } = req.body as VerifyCredentialRequest;

        if (!jwt_vc) {
            return res.status(400).json({ error: 'jwt_vc is required' });
        }

        const result = await affinidiService.verifyCredential(jwt_vc);

        const response: VerifyCredentialResponse = result;

        res.json(response);
    } catch (error: any) {
        logger.error(`Failed to verify credential: ${error}`);
        const response: VerifyCredentialResponse = {
            valid: false,
            verified: false,
            error: error.message,
        };
        res.json(response);
    }
});

// Error handling middleware
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
    logger.error(`Unhandled error: ${err.message}`);
    res.status(500).json({
        error: 'Internal server error',
        detail: err.message,
    });
});

// ============================================================================
// Server Initialization
// ============================================================================

async function startServer() {
    try {
        // Validate environment variables
        const projectId = process.env.PROJECT_ID;
        const tokenId = process.env.TOKEN_ID;
        const passphrase = process.env.PASSPHRASE;
        const privateKey = process.env.PRIVATE_KEY;

        if (!projectId || !tokenId || !passphrase || !privateKey) {
            throw new Error(
                'Missing Affinidi credentials in .env file. Set PROJECT_ID, TOKEN_ID, PASSPHRASE, PRIVATE_KEY'
            );
        }

        // Initialize Affinidi service
        affinidiService = new AffinidiService({
            projectId,
            tokenId,
            passphrase,
            privateKey,
        });

        logger.info('Affinidi Wallet Service initialized successfully');

        // Start server
        const port = parseInt(process.env.PORT || '8454', 10);
        app.listen(port, '0.0.0.0', () => {
            logger.info(`Trusted Service running on port ${port}`);
            logger.info('Your server http://localhost:' + port);
        });
    } catch (error) {
        logger.error(`Failed to start server: ${error}`);
        process.exit(1);
    }
}

// Handle graceful shutdown
process.on('SIGTERM', () => {
    logger.info('SIGTERM signal received: closing server');
    process.exit(0);
});

process.on('SIGINT', () => {
    logger.info('SIGINT signal received: closing server');
    process.exit(0);
});

// Start the server
startServer();
