# Mastercard API Integration Documentation

This document describes the integration of Mastercard's Card on File (CoF) Tokenization and Secure Card on File (SCoF) Authentication APIs into the Enhanced Business Agent chat application.

## Overview

The Mastercard integration adds two key capabilities to the payment flow:

1. **Card on File Tokenization**: Securely tokenize payment cards during user registration
2. **Secure Card on File Authentication**: Add an additional layer of authentication during payment transactions

**Important**: This integration is **optional** and **disabled by default**. The application works fully without Mastercard APIs enabled.

## Architecture

### Integration Points

The Mastercard integration affects **only the chat backend** - there are no changes to the merchant frontend or backend.

```
┌─────────────────────────────────────────────────────────────┐
│                    Chat Backend (Port 8452)                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  User Registration Flow                                 │ │
│  │  ─────────────────────                                  │ │
│  │  1. User registers with passkey                         │ │
│  │  2. Default card created (5123 1212 2232 5678)         │ │
│  │  3. [IF ENABLED] Card tokenized with Mastercard API    │ │
│  │  4. Token stored in database                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Payment Flow                                           │ │
│  │  ─────────────                                          │ │
│  │  1. User confirms checkout with passkey                 │ │
│  │  2. [IF ENABLED] Mastercard authentication initiated   │ │
│  │  3. User completes Mastercard authentication (OTP)     │ │
│  │  4. Payment mandate processed                           │ │
│  │  5. Standard AP2/UCP payment flow continues            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### New Components

1. **mastercard_client.py** - Mastercard API client with OAuth 1.0a authentication
2. **Database Models** - Extended PaymentCard and new MastercardAuthenticationChallenge models
3. **API Endpoints**:
   - `POST /api/payment/verify-mastercard-auth` - Verify Mastercard authentication challenges

## Configuration

### Environment Variables

Add these to `/chat-backend/.env`:

```bash
# Mastercard API Integration (Optional - Default: OFF)
# Set to "true" to enable Mastercard Card on File tokenization and authentication
MASTERCARD_ENABLED=false

# Mastercard API Credentials (Required only if MASTERCARD_ENABLED=true)
# Get these from https://developer.mastercard.com/
MASTERCARD_CONSUMER_KEY=your_consumer_key_here
MASTERCARD_SIGNING_KEY_PATH=/path/to/your/signing-key.pem

# Mastercard Environment
MASTERCARD_SANDBOX=true
```

### Getting Mastercard API Credentials

1. **Sign up** at [Mastercard Developers](https://developer.mastercard.com/)
2. **Create a project** for Card on File and Secure Card on File APIs
3. **Generate credentials**:
   - Consumer Key (API key)
   - Signing Key (.p12 or .pem file)
4. **Download the signing key** and save it securely
5. **Convert .p12 to .pem** if needed:
   ```bash
   openssl pkcs12 -in signing-key.p12 -out signing-key.pem -nodes
   ```

### Enabling the Integration

To enable Mastercard integration:

1. Set `MASTERCARD_ENABLED=true` in `.env`
2. Provide valid `MASTERCARD_CONSUMER_KEY`
3. Provide path to signing key in `MASTERCARD_SIGNING_KEY_PATH`
4. Restart the chat backend

To disable:

1. Set `MASTERCARD_ENABLED=false` (or remove the variable)
2. Restart the chat backend

## API Reference

### Mastercard Tokenization Client

Location: [mastercard_client.py](chat-backend/mastercard_client.py)

#### `tokenize_card(card_number, expiry_month, expiry_year, ...)`

Tokenizes a payment card using Mastercard MDES (Mastercard Digital Enablement Service).

**Request:**
```python
token_response = await mastercard.tokenization.tokenize_card(
    card_number="5123121222325678",
    expiry_month=12,
    expiry_year=2028,
    cardholder_name="John Doe"
)
```

**Response:**
```python
{
    "token": "4111111111111111",  # Network token
    "token_unique_reference": "DWSPMC000...",
    "pan_last_four": "5678",
    "card_network": "mastercard",
    "expiry_month": 12,
    "expiry_year": 2028,
    "token_assurance_level": "high"
}
```

### Mastercard Authentication Client

#### `initiate_authentication(token, amount, currency, ...)`

Initiates authentication for a card-on-file transaction.

**Request:**
```python
auth_response = await mastercard.authentication.initiate_authentication(
    token="DWSPMC000...",
    amount=15.99,
    currency="USD",
    merchant_id="merchant-001",
    transaction_id="cs_abc123"
)
```

**Response:**
```python
{
    "authentication_required": True,
    "authentication_method": "otp",  # or "biometric", "none"
    "challenge_id": "ch_xyz789",
    "status": "pending"
}
```

#### `verify_authentication(challenge_id, verification_code)`

Verifies an authentication challenge.

**Request:**
```python
verify_result = await mastercard.authentication.verify_authentication(
    challenge_id="ch_xyz789",
    verification_code="123456"
)
```

**Response:**
```python
{
    "verified": True,
    "status": "approved",
    "message": "Authentication successful"
}
```

## Database Schema Changes

### PaymentCard Model Extensions

New fields added to `payment_cards` table:

```python
mastercard_token = Column(String)              # Network token
mastercard_token_ref = Column(String)          # Token unique reference
mastercard_token_assurance = Column(String)    # Token assurance level
tokenization_date = Column(DateTime)           # When tokenized
is_tokenized = Column(Boolean, default=False)  # Tokenization flag
```

### MastercardAuthenticationChallenge Model

New table: `mastercard_auth_challenges`

```python
id = Column(String, primary_key=True)
payment_mandate_id = Column(String, ForeignKey("payment_mandates.id"))
challenge_id = Column(String)                  # Mastercard challenge ID
transaction_id = Column(String)                # Transaction ID
authentication_method = Column(String)         # "otp", "biometric", etc.
status = Column(String)                        # "pending", "approved", "declined"
verification_code = Column(String)             # Temporary OTP storage
attempts = Column(Integer, default=0)
created_at = Column(DateTime)
verified_at = Column(DateTime)
expires_at = Column(DateTime)
raw_response = Column(Text)                    # JSON response from API
```

## Payment Flow

### Standard Flow (Mastercard Disabled)

```
1. User confirms checkout
2. Passkey signature collected
3. Payment mandate sent to merchant
4. [Optional] Standard OTP challenge
5. Payment processed
6. Receipt returned
```

### Enhanced Flow (Mastercard Enabled)

```
1. User confirms checkout
2. Passkey signature collected
3. Check if card is tokenized (is_tokenized=True)
4. If tokenized:
   a. Initiate Mastercard authentication
   b. If authentication required:
      - Create MastercardAuthenticationChallenge
      - Return challenge to user
      - User enters verification code
      - POST /api/payment/verify-mastercard-auth
      - Verify with Mastercard
      - On success, continue to step 5
5. Payment mandate sent to merchant
6. [Optional] Standard OTP challenge (separate from Mastercard)
7. Payment processed
8. Receipt returned
```

## API Endpoints

### POST /api/payment/verify-mastercard-auth

Verify a Mastercard authentication challenge.

**Request:**
```json
{
  "challenge_id": "uuid",
  "verification_code": "123456",
  "mandate_id": "PM-ABC123",
  "user_email": "user@example.com"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "receipt": {...},
  "message": "Payment completed successfully!"
}
```

**Response (Additional OTP Required):**
```json
{
  "status": "otp_required",
  "otp_challenge": {...},
  "message": "Additional OTP verification required"
}
```

**Response (Failed):**
```json
{
  "status": "failed",
  "message": "Authentication verification failed"
}
```

## Security Considerations

### OAuth 1.0a Signature

Mastercard APIs use OAuth 1.0a with RSA-SHA256 signature method:

- Each request is signed with your private key
- Signature includes request URL, method, parameters, and body hash
- Prevents request tampering and replay attacks

### Token Storage

- Network tokens are stored in the database (not encrypted - tokens are not sensitive)
- Original card numbers remain encrypted with Fernet
- Tokens are bound to your merchant ID and cannot be used elsewhere

### Authentication Challenges

- Challenges expire after 5 minutes
- Maximum 3 verification attempts
- Verification codes stored temporarily (should be hashed in production)

## Testing

### Sandbox Environment

When `MASTERCARD_SANDBOX=true`, all API calls go to:
- `https://sandbox.api.mastercard.com`

Test cards for sandbox:
- **Mastercard**: 5123 1212 2232 5678 (already used as default card)
- Expiry: Any future date
- CVV: Any 3 digits

### Testing Without Mastercard APIs

Simply set `MASTERCARD_ENABLED=false` or leave credentials blank. The application works normally with:
- Encrypted card storage
- WebAuthn passkey authentication
- Standard AP2 payment flow
- OTP challenges (simulated)

### Testing With Mastercard APIs

1. **Set credentials** in `.env`
2. **Enable integration**: `MASTERCARD_ENABLED=true`
3. **Restart chat backend**: `./stop-split.sh && ./start-split.sh`
4. **Register a new user** - card will be tokenized automatically
5. **Make a purchase** - Mastercard authentication may be triggered
6. **Check logs** for tokenization/authentication events:
   ```bash
   tail -f logs/chat-backend.log | grep -i mastercard
   ```

## Troubleshooting

### Integration Not Working

**Check environment variables:**
```bash
cd chat-backend
cat .env | grep MASTERCARD
```

**Check logs:**
```bash
tail -f ../logs/chat-backend.log
```

**Look for:**
- "Mastercard API integration is disabled" - Integration is off
- "Mastercard API integration enabled" - Integration is on
- "Tokenizing card for user..." - Tokenization in progress
- "Card tokenized successfully..." - Tokenization succeeded
- "Failed to tokenize card..." - Tokenization error

### OAuth Signature Errors

**Error**: "Invalid signature" or 401 responses

**Solutions**:
- Verify signing key is in PEM format
- Check consumer key matches the one in Mastercard portal
- Ensure signing key path is absolute, not relative
- Verify key file has correct permissions (readable by app)

### Tokenization Fails

If tokenization fails during registration:
- The app **continues normally** with encrypted card storage
- Check error in logs
- Verify sandbox credentials are correct
- Card is still usable, just not tokenized

### Authentication Challenges Not Appearing

If Mastercard authentication is not triggered:
- Check `is_tokenized=True` for the payment card
- Verify `MASTERCARD_ENABLED=true`
- Check authentication API is responding (see logs)
- Some transactions may not require authentication (based on risk)

## Migration Guide

### Enabling on Existing Installation

1. **Backup database**:
   ```bash
   cp chat-backend/chat_app.db chat-backend/chat_app.db.backup
   ```

2. **Add environment variables** to `.env`

3. **Restart application**:
   ```bash
   ./stop-split.sh
   ./start-split.sh
   ```

4. **Database will auto-migrate** with new columns

5. **Existing cards remain untokenized** - only new registrations are tokenized

6. **Test with new registration** to verify tokenization

### Disabling the Integration

1. **Set `MASTERCARD_ENABLED=false`**

2. **Restart application**

3. **Existing tokens remain** in database but won't be used

4. **All payments use** standard encrypted card flow

## Support

### Documentation

- [Mastercard Developers](https://developer.mastercard.com/)
- [Card on File Tokenization](https://developer.mastercard.com/mastercard-checkout-solutions/documentation/use-cases/card-on-file/)
- [Secure Card on File Authentication](https://developer.mastercard.com/mastercard-checkout-solutions/documentation/token-authentication/secure-card-on-file/by-mastercard/use-case1/)
- [OAuth 1.0a Security](https://developer.mastercard.com/platform/documentation/security-and-authentication/)

### Code References

- **Mastercard Client**: [chat-backend/mastercard_client.py](chat-backend/mastercard_client.py)
- **Database Models**: [chat-backend/database.py](chat-backend/database.py)
- **Registration Flow**: [chat-backend/main.py:416-520](chat-backend/main.py#L416-L520)
- **Payment Flow**: [chat-backend/main.py:774-932](chat-backend/main.py#L774-L932)
- **Auth Verification**: [chat-backend/main.py:1021-1156](chat-backend/main.py#L1021-L1156)

## FAQ

**Q: Is Mastercard integration required?**
A: No, it's completely optional. The app works fully without it.

**Q: What happens if Mastercard API is down?**
A: Tokenization/authentication errors are caught and logged. The payment flow falls back to standard encrypted card processing.

**Q: Can I use this in production?**
A: Yes, but:
- Switch `MASTERCARD_SANDBOX=false`
- Use production credentials
- Hash verification codes instead of plain text storage
- Implement proper key management (KMS)
- Add monitoring and alerting

**Q: Does this affect the merchant backend?**
A: No, the merchant backend is unchanged. Mastercard integration is entirely within the chat backend (consumer agent).

**Q: What about other card networks (Visa, Amex)?**
A: Currently only Mastercard cards are tokenized. Other cards use standard encrypted storage. You could extend the integration to support Visa Token Service or other networks.

**Q: How do I get sandbox credentials?**
A: Sign up at https://developer.mastercard.com/, create a project, and generate sandbox credentials. It's free for development.

---

**Built with Mastercard APIs** - Secure tokenization and authentication for card-on-file payments.
