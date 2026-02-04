/**
 * Test script for Trusted Service
 * Tests DID:web wallet creation, credential signing, and verification
 */

import dotenv from 'dotenv';
import { AffinidiService } from './affinidi-service';
import { logger } from './logger';

dotenv.config();

async function testSignerService() {
    logger.info('========================================');
    logger.info('Testing Trusted Service');
    logger.info('========================================');

    try {
        // Validate environment variables
        const projectId = process.env.PROJECT_ID;
        const tokenId = process.env.TOKEN_ID;
        const passphrase = process.env.PASSPHRASE;
        const privateKey = process.env.PRIVATE_KEY;

        if (!projectId || !tokenId || !passphrase || !privateKey) {
            throw new Error('Missing Affinidi credentials in .env file');
        }

        // Initialize service
        logger.info('Initializing Affinidi Wallet Service...');
        const service = new AffinidiService({
            projectId,
            tokenId,
            passphrase,
            privateKey,
        });

        // Test domain
        const testDomain = 'localhost:8453';
        logger.info(`\nTest domain: ${testDomain}`);

        // Test 1: Create/Get Wallet
        logger.info('\n--- Test 1: Create/Get DID:web Wallet ---');
        const walletData = await service.createOrGetWallet(testDomain);
        logger.info(`✓ Wallet ID: ${walletData.wallet_id}`);
        logger.info(`✓ DID: ${walletData.did}`);
        logger.info(`✓ Signing Key ID: ${walletData.signing_key_id}`);

        // Test 2: Sign Credential
        logger.info('\n--- Test 2: Sign Credential ---');
        const unsignedCredential = {
            '@context': ['https://www.w3.org/2018/credentials/v1'],
            type: ['VerifiableCredential'],
            issuer: walletData.did,
            issuanceDate: new Date().toISOString(),
            credentialSubject: {
                id: 'did:example:subject123',
                name: 'Test User',
                email: 'test@example.com',
            },
        };

        const signedCredential = await service.signCredential(testDomain, unsignedCredential);
        logger.info(`✓ Signed credential (JWT): ${signedCredential.substring(0, 50)}...`);

        // Test 3: Verify Credential
        logger.info('\n--- Test 3: Verify Credential ---');
        const verificationResult = await service.verifyCredential(signedCredential);
        logger.info(`✓ Valid: ${verificationResult.valid}`);
        logger.info(`✓ Verified: ${verificationResult.verified}`);
        if (verificationResult.error) {
            logger.warn(`  Warning: ${verificationResult.error}`);
        }

        logger.info('\n========================================');
        logger.info('All tests completed successfully!');
        logger.info('========================================');

    } catch (error) {
        logger.error(`Test failed: ${error}`);
        process.exit(1);
    }
}

// Run tests
testSignerService();
