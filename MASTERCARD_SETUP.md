# Mastercard API - Quick Setup Guide

This guide will help you set up Mastercard API credentials once you receive them from the Mastercard Developer Portal.

## Prerequisites

You should have received:
1. **Consumer Key** (also called API Key)
2. **Signing Key File** (.p12 or .pem format)
3. **Signing Key Password** (if applicable)

## Setup Steps

### 1. Prepare the Signing Key

If you received a `.p12` file, convert it to `.pem` format:

```bash
# Navigate to chat-backend directory
cd /home/coder/WorkingSpace/ucp-sample/enhanced-app/chat-backend

# Create a keys directory
mkdir -p keys

# Convert .p12 to .pem (you'll be prompted for the .p12 password)
openssl pkcs12 -in /path/to/your-signing-key.p12 -out keys/mastercard-signing-key.pem -nodes
```

If you already have a `.pem` file, just copy it:

```bash
cp /path/to/your-signing-key.pem keys/mastercard-signing-key.pem
```

Set proper permissions:

```bash
chmod 600 keys/mastercard-signing-key.pem
```

### 2. Update Environment Variables

Edit the chat backend `.env` file:

```bash
nano /home/coder/WorkingSpace/ucp-sample/enhanced-app/chat-backend/.env
```

Update these variables:

```env
# Enable Mastercard Integration
MASTERCARD_ENABLED=true

# Add your Consumer Key
MASTERCARD_CONSUMER_KEY=your_consumer_key_here

# Path to signing key (use absolute path)
MASTERCARD_SIGNING_KEY_PATH=/home/coder/WorkingSpace/ucp-sample/enhanced-app/chat-backend/keys/mastercard-signing-key.pem

# Sandbox mode (set to false for production)
MASTERCARD_SANDBOX=true
```

Save and exit (Ctrl+X, then Y, then Enter).

### 3. Verify Configuration

Check that the signing key is readable:

```bash
cat /home/coder/WorkingSpace/ucp-sample/enhanced-app/chat-backend/keys/mastercard-signing-key.pem
```

You should see something like:
```
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...
...
-----END PRIVATE KEY-----
```

### 4. Restart the Application

```bash
cd /home/coder/WorkingSpace/ucp-sample/enhanced-app

# Stop all services
./stop-split.sh

# Start all services
./start-split.sh
```

### 5. Verify Integration

Check the logs to confirm Mastercard integration is enabled:

```bash
tail -f logs/chat-backend.log | grep -i mastercard
```

You should see:
```
Mastercard API client initialized successfully (sandbox mode)
```

If you see:
```
Mastercard API integration is disabled (MASTERCARD_ENABLED=false)
```

Then the `MASTERCARD_ENABLED` flag is not set to `true`.

If you see:
```
Mastercard API enabled but credentials not configured
```

Then either the consumer key or signing key path is incorrect.

### 6. Test the Integration

1. **Register a new user** in the chat interface
2. **Watch the logs** for tokenization:

```bash
tail -f logs/chat-backend.log | grep -i "tokeniz"
```

You should see:
```
Tokenizing card for user user@example.com with Mastercard API
Card tokenized successfully for user@example.com: DWSPMC000...
User registered: user@example.com with default card ending 5678 (tokenized: True)
```

3. **Make a purchase** to test authentication
4. **Check for authentication logs**:

```bash
tail -f logs/chat-backend.log | grep -i "mastercard auth"
```

## Troubleshooting

### "Invalid signature" or 401 errors

**Problem**: OAuth signature verification failed

**Solutions**:
- Verify the consumer key is correct
- Ensure signing key is in PEM format
- Check that the signing key matches the consumer key
- Verify file permissions: `chmod 600 keys/mastercard-signing-key.pem`

### "Tokenization failed"

**Problem**: Card tokenization API returned an error

**Solutions**:
- Check sandbox credentials are valid
- Verify you have access to MDES API in Mastercard portal
- Check logs for specific error message
- Note: App continues to work with encrypted card storage if tokenization fails

### Integration not activating

**Problem**: Logs show "Mastercard API integration is disabled"

**Solutions**:
- Verify `MASTERCARD_ENABLED=true` (not "True" or "TRUE")
- Check `.env` file has no spaces around `=`
- Restart the application after changing `.env`
- Verify you edited the correct `.env` file (chat-backend, not merchant-backend)

### Signing key not found

**Problem**: "Signing key not found at /path/to/key.pem"

**Solutions**:
- Use absolute path, not relative path
- Verify file exists: `ls -la /path/to/key.pem`
- Check file permissions: `chmod 600 /path/to/key.pem`

## Quick Reference

### File Locations

- **Environment Config**: `/home/coder/WorkingSpace/ucp-sample/enhanced-app/chat-backend/.env`
- **Signing Key**: `/home/coder/WorkingSpace/ucp-sample/enhanced-app/chat-backend/keys/mastercard-signing-key.pem`
- **Logs**: `/home/coder/WorkingSpace/ucp-sample/enhanced-app/logs/chat-backend.log`
- **Mastercard Client**: `/home/coder/WorkingSpace/ucp-sample/enhanced-app/chat-backend/mastercard_client.py`

### Environment Variables

```env
MASTERCARD_ENABLED=true                    # Enable/disable integration
MASTERCARD_CONSUMER_KEY=<your_key>         # API consumer key
MASTERCARD_SIGNING_KEY_PATH=<path_to_pem>  # Path to signing key
MASTERCARD_SANDBOX=true                    # Use sandbox (true) or production (false)
```

### Log Commands

```bash
# Watch all Mastercard-related logs
tail -f logs/chat-backend.log | grep -i mastercard

# Watch tokenization logs
tail -f logs/chat-backend.log | grep -i tokeniz

# Watch authentication logs
tail -f logs/chat-backend.log | grep -i "mastercard auth"

# Watch all logs
tail -f logs/chat-backend.log
```

### Restart Commands

```bash
cd /home/coder/WorkingSpace/ucp-sample/enhanced-app

# Stop services
./stop-split.sh

# Start services
./start-split.sh

# Or restart in one command
./stop-split.sh && ./start-split.sh
```

## Testing Checklist

- [ ] Consumer key added to `.env`
- [ ] Signing key converted to PEM format
- [ ] Signing key saved in `chat-backend/keys/` directory
- [ ] Signing key path is absolute in `.env`
- [ ] `MASTERCARD_ENABLED=true` in `.env`
- [ ] Application restarted
- [ ] Logs show "Mastercard API client initialized successfully"
- [ ] New user registration tokenizes card
- [ ] Logs show "Card tokenized successfully"
- [ ] Payment flow triggers Mastercard authentication (may not always trigger)

## Support

For detailed documentation, see:
- [Mastercard Integration Guide](MASTERCARD_INTEGRATION.md)
- [Main README](README.md)

For Mastercard API issues:
- [Mastercard Developer Portal](https://developer.mastercard.com/)
- [Support](https://developer.mastercard.com/support)

---

**Ready to test!** Once credentials are configured, register a new user to see card tokenization in action.
