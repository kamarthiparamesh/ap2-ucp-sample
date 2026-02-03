import { useState } from 'react'
import axios from 'axios'
import { CreditCard, Shield, CheckCircle, AlertCircle, ArrowLeft } from 'lucide-react'

interface RegisterPageProps {
  onRegistrationComplete: (email: string) => void
  onBackToChat: () => void
}

// Helper function to convert ArrayBuffer to URL-safe base64
function arrayBufferToUrlSafeBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  // Convert to base64 and make it URL-safe
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

function RegisterPage({ onRegistrationComplete, onBackToChat }: RegisterPageProps) {
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [step, setStep] = useState<'form' | 'passkey'>('form')

  const startRegistration = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !displayName) {
      setError('Please fill in all fields')
      return
    }

    // Check if WebAuthn is supported
    if (!window.PublicKeyCredential) {
      setError('Passkey authentication is not supported in this browser. Please use a modern browser like Chrome, Edge, Firefox, or Safari.')
      return
    }

    setLoading(true)
    setError('')

    try {
      // Step 1: Get WebAuthn challenge
      const challengeResponse = await axios.post('/api/auth/challenge', {
        email,
        display_name: displayName
      })

      const { challenge } = challengeResponse.data

      // Step 2: Create WebAuthn credential (passkey)
      setStep('passkey')

      // Convert URL-safe base64 to standard base64 for atob()
      const base64Challenge = challenge.replace(/-/g, '+').replace(/_/g, '/').padEnd(
        challenge.length + (4 - (challenge.length % 4)) % 4, '='
      )

      const publicKeyCredentialCreationOptions: PublicKeyCredentialCreationOptions = {
        challenge: Uint8Array.from(atob(base64Challenge), c => c.charCodeAt(0)),
        rp: {
          name: "AI Shopping Assistant",
          id: window.location.hostname === 'localhost' ? 'localhost' : window.location.hostname
        },
        user: {
          id: Uint8Array.from(email, c => c.charCodeAt(0)),
          name: email,
          displayName: displayName
        },
        pubKeyCredParams: [
          { alg: -7, type: "public-key" },  // ES256
          { alg: -257, type: "public-key" }  // RS256
        ],
        authenticatorSelection: {
          // Removed authenticatorAttachment to allow both platform and cross-platform authenticators
          requireResidentKey: false,
          userVerification: "preferred"  // Changed from "required" to "preferred" for broader compatibility
        },
        timeout: 60000,
        attestation: "none"
      }

      const credential = await navigator.credentials.create({
        publicKey: publicKeyCredentialCreationOptions
      }) as PublicKeyCredential

      if (!credential) {
        throw new Error('Failed to create passkey')
      }

      const attestationResponse = credential.response as AuthenticatorAttestationResponse

      // Step 3: Register with backend
      const registrationData = {
        email,
        display_name: displayName,
        challenge,
        credential_id: arrayBufferToUrlSafeBase64(credential.rawId),
        client_data_json: arrayBufferToUrlSafeBase64(attestationResponse.clientDataJSON),
        attestation_object: arrayBufferToUrlSafeBase64(attestationResponse.attestationObject)
      }

      await axios.post('/api/auth/register', registrationData)

      setSuccess(true)
      setTimeout(() => {
        onRegistrationComplete(email)
      }, 2000)

    } catch (err: any) {
      console.error('Registration error:', err)
      if (err.name === 'NotAllowedError') {
        setError('Passkey creation was cancelled or not allowed')
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail)
      } else {
        setError('Registration failed. Please try again.')
      }
      setStep('form')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-blue-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center animate-slide-up">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-12 h-12 text-green-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-800 mb-2">Registration Complete!</h2>
          <p className="text-gray-600 mb-4">
            Your account and payment method have been set up successfully.
          </p>
          <div className="bg-blue-50 rounded-lg p-4 mb-6">
            <p className="text-sm text-gray-700">
              <strong>Default Card:</strong> •••• 5678 (Mastercard)
            </p>
          </div>
          <p className="text-sm text-gray-500">Redirecting to chat...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        {/* Header */}
        <button
          onClick={onBackToChat}
          className="flex items-center text-gray-600 hover:text-gray-800 mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Chat
        </button>

        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-800 mb-2">Create Account</h1>
          <p className="text-gray-600">Register with passkey authentication</p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6 flex items-start">
            <AlertCircle className="w-5 h-5 text-red-600 mr-3 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Registration Form */}
        <form onSubmit={startRegistration} className="space-y-6">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
              Email Address
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
              placeholder="your@email.com"
              required
              disabled={loading}
            />
          </div>

          <div>
            <label htmlFor="displayName" className="block text-sm font-medium text-gray-700 mb-2">
              Full Name
            </label>
            <input
              type="text"
              id="displayName"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="input-field"
              placeholder="John Doe"
              required
              disabled={loading}
            />
          </div>

          {/* Default Card Info */}
          <div className="bg-gradient-to-r from-gray-800 to-gray-900 rounded-xl p-6 text-white">
            <div className="flex items-center justify-between mb-4">
              <CreditCard className="w-8 h-8" />
              <div className="text-right">
                <p className="text-xs text-gray-400">Default Test Card</p>
                <p className="text-sm font-medium">Mastercard</p>
              </div>
            </div>
            <p className="text-lg tracking-wider mb-2">•••• •••• •••• 5678</p>
            <p className="text-xs text-gray-400">This test card will be added to your account</p>
          </div>

          {/* Passkey Info */}
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="flex items-start">
              <Shield className="w-5 h-5 text-blue-600 mr-3 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-gray-800 mb-1">Secure Passkey Authentication</p>
                <p className="text-xs text-gray-600">
                  {step === 'form'
                    ? 'You\'ll be prompted to create a passkey using your device\'s biometric authentication.'
                    : 'Please complete the passkey creation on your device...'}
                </p>
              </div>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full flex items-center justify-center space-x-2"
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                <span>{step === 'passkey' ? 'Waiting for passkey...' : 'Creating account...'}</span>
              </>
            ) : (
              <>
                <Shield className="w-5 h-5" />
                <span>Register with Passkey</span>
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <p className="text-xs text-gray-500 text-center mt-6">
          By registering, you agree to secure payment processing via AP2 protocol
        </p>
      </div>
    </div>
  )
}

export default RegisterPage
