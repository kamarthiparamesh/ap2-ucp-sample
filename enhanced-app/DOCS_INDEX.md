# Enhanced Business Agent - Documentation Index

Complete documentation for the Enhanced Business Agent with UCP, AP2, and Mastercard integration.

## 📚 Main Documentation

### [README.md](README.md)
**Complete application overview and quick start guide**
- Architecture diagram
- UCP + AP2 integration details
- Installation and setup
- Port allocation
- Configuration examples
- Production deployment guide
- Troubleshooting

### [UCP-KNOWLEDGE-BASE.md](UCP-KNOWLEDGE-BASE.md)
**Universal Commerce Protocol knowledge base**
- UCP specification details
- Protocol standards
- Service discovery
- Checkout session management

## 💳 Mastercard Integration

### [MASTERCARD_SUMMARY.md](MASTERCARD_SUMMARY.md) ⭐ **START HERE**
**Quick overview of what was built**
- What was implemented
- How it works
- Benefits and features
- Files modified
- Next steps

### [MASTERCARD_SETUP.md](MASTERCARD_SETUP.md) 🚀 **SETUP GUIDE**
**Step-by-step setup instructions**
- Converting signing keys (.p12 to .pem)
- Environment variable configuration
- Verification steps
- Testing checklist
- Troubleshooting common issues

### [MASTERCARD_INTEGRATION.md](MASTERCARD_INTEGRATION.md) 📖 **REFERENCE**
**Complete technical documentation (4,500+ words)**
- API reference
- Architecture diagrams
- Database schema changes
- Payment flow details
- Security considerations
- Testing instructions
- FAQ

## 🗂️ Documentation by Topic

### Getting Started
1. [README.md](README.md#-quick-start) - Quick Start
2. [README.md](README.md#-architecture-overview) - Architecture Overview
3. [README.md](README.md#-project-structure) - Project Structure

### Mastercard Setup (when credentials available)
1. [MASTERCARD_SUMMARY.md](MASTERCARD_SUMMARY.md) - Overview
2. [MASTERCARD_SETUP.md](MASTERCARD_SETUP.md) - Setup Guide
3. [MASTERCARD_INTEGRATION.md](MASTERCARD_INTEGRATION.md#configuration) - Configuration Details

### Payment Flows
- [README.md](README.md#-ap2-payment-protocol-integration) - AP2 Payment Overview
- [MASTERCARD_INTEGRATION.md](MASTERCARD_INTEGRATION.md#payment-flow) - Mastercard Payment Flow
- [README.md](README.md#security-features) - Security Features

### API Reference
- [README.md](README.md#api-endpoints) - Chat Backend Endpoints
- [MASTERCARD_INTEGRATION.md](MASTERCARD_INTEGRATION.md#api-reference) - Mastercard API Reference
- [MASTERCARD_INTEGRATION.md](MASTERCARD_INTEGRATION.md#api-endpoints) - Payment Endpoints

### Troubleshooting
- [README.md](README.md#-troubleshooting) - General Issues
- [MASTERCARD_SETUP.md](MASTERCARD_SETUP.md#troubleshooting) - Mastercard Setup Issues
- [MASTERCARD_INTEGRATION.md](MASTERCARD_INTEGRATION.md#troubleshooting) - Integration Problems

### Database
- [MASTERCARD_INTEGRATION.md](MASTERCARD_INTEGRATION.md#database-schema-changes) - Schema Changes
- [README.md](README.md#-chat-backend-features) - Database Overview

## 🔍 Quick Links

### For Users
- **Just want to test the app?** → [README.md Quick Start](README.md#-quick-start)
- **Have Mastercard credentials?** → [MASTERCARD_SETUP.md](MASTERCARD_SETUP.md)
- **Want to understand Mastercard integration?** → [MASTERCARD_SUMMARY.md](MASTERCARD_SUMMARY.md)

### For Developers
- **API Documentation** → [MASTERCARD_INTEGRATION.md API Reference](MASTERCARD_INTEGRATION.md#api-reference)
- **Architecture Details** → [README.md Architecture](README.md#-architecture-overview)
- **Database Models** → [MASTERCARD_INTEGRATION.md Database](MASTERCARD_INTEGRATION.md#database-schema-changes)
- **Code References** → [MASTERCARD_INTEGRATION.md Code Files](MASTERCARD_INTEGRATION.md#support)

### For Testing
- **Without Mastercard** → [MASTERCARD_INTEGRATION.md Testing Without](MASTERCARD_INTEGRATION.md#testing-without-mastercard-apis)
- **With Mastercard** → [MASTERCARD_INTEGRATION.md Testing With](MASTERCARD_INTEGRATION.md#testing-with-mastercard-apis)
- **Sandbox Environment** → [MASTERCARD_INTEGRATION.md Sandbox](MASTERCARD_INTEGRATION.md#sandbox-environment)

## 📂 Code Files Reference

### Mastercard Integration
- `chat-backend/mastercard_client.py` - Mastercard API client (600+ lines)
- `chat-backend/database.py` - Database models with Mastercard fields
- `chat-backend/main.py` - Integration endpoints
- `chat-backend/.env` - Configuration (not in git)

### Frontend
- `frontend/chat/` - Customer-facing chat interface
- `frontend/merchant-portal/` - Admin product management

### Backend Services
- `chat-backend/` - UCP Client + AP2 Consumer Agent + Credentials Provider
- `merchant-backend/` - UCP Server + AP2 Merchant Agent

## 🎯 Common Tasks

### Enable Mastercard Integration
```bash
# 1. Edit chat-backend/.env
MASTERCARD_ENABLED=true
MASTERCARD_CONSUMER_KEY=your_key
MASTERCARD_SIGNING_KEY_PATH=/path/to/key.pem

# 2. Restart
./stop-split.sh && ./start-split.sh
```
📖 [Full Setup Guide](MASTERCARD_SETUP.md)

### Check Logs
```bash
# All logs
tail -f logs/chat-backend.log

# Mastercard only
tail -f logs/chat-backend.log | grep -i mastercard
```
📖 [Troubleshooting](MASTERCARD_SETUP.md#troubleshooting)

### Test Registration
```bash
# Watch tokenization
tail -f logs/chat-backend.log | grep -i tokeniz

# Then register via UI at http://localhost:8450
```
📖 [Testing Guide](MASTERCARD_INTEGRATION.md#testing)

## 📊 Documentation Stats

| Document | Size | Purpose |
|----------|------|---------|
| README.md | ~3,000 words | Main application guide |
| MASTERCARD_INTEGRATION.md | ~4,500 words | Complete technical reference |
| MASTERCARD_SETUP.md | ~1,200 words | Quick setup instructions |
| MASTERCARD_SUMMARY.md | ~2,000 words | Implementation overview |
| UCP-KNOWLEDGE-BASE.md | Varies | UCP protocol details |

**Total**: ~11,000+ words of documentation

## 🆘 Getting Help

### Documentation Issues
- Check the [FAQ](MASTERCARD_INTEGRATION.md#faq)
- Review [Troubleshooting](MASTERCARD_SETUP.md#troubleshooting)
- See [Common Issues](README.md#-troubleshooting)

### Mastercard API Support
- [Mastercard Developer Portal](https://developer.mastercard.com/)
- [Card on File API Docs](https://developer.mastercard.com/mastercard-checkout-solutions/documentation/use-cases/card-on-file/)
- [Secure Card on File Docs](https://developer.mastercard.com/mastercard-checkout-solutions/documentation/token-authentication/secure-card-on-file/by-mastercard/use-case1/)

### Application Support
- Check application logs in `logs/` directory
- Review API documentation at `/docs` endpoint
- Test with sandbox credentials first

---

**Last Updated**: January 2026

**Quick Navigation**: [Main README](README.md) | [Mastercard Summary](MASTERCARD_SUMMARY.md) | [Setup Guide](MASTERCARD_SETUP.md) | [API Reference](MASTERCARD_INTEGRATION.md)
