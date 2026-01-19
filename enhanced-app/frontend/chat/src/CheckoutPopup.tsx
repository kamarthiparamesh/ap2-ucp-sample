import { useState, useEffect } from 'react'
import axios from 'axios'
import { X, CreditCard, ShoppingCart, Shield, CheckCircle, AlertCircle, Loader } from 'lucide-react'

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

interface CheckoutPopupProps {
  isOpen: boolean
  onClose: () => void
  sessionId: string
  userEmail: string
  onPaymentSuccess?: (paymentId: string, total: number, items: CartItem[]) => void
}

interface CartItem {
  id: string
  sku: string
  title: string
  price: number
  quantity: number
  image_url?: string
}

interface PaymentCard {
  card_last_four: string
  card_network: string
}

interface PrepareCheckoutResponse {
  mandate_id: string
  mandate_data: any
  cart_total: number
  cart_items: CartItem[]
  default_card: PaymentCard
}

function CheckoutPopup({ isOpen, onClose, sessionId, userEmail, onPaymentSuccess }: CheckoutPopupProps) {
  const [loading, setLoading] = useState(false)
  const [preparing, setPreparing] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [otpRequired, setOtpRequired] = useState(false)
  const [otpCode, setOtpCode] = useState('')
  const [otpMessage, setOtpMessage] = useState('')

  const [checkoutData, setCheckoutData] = useState<PrepareCheckoutResponse | null>(null)
  const [mandateId, setMandateId] = useState('')
  const [paymentId, setPaymentId] = useState('')

  useEffect(() => {
    if (isOpen) {
      prepareCheckout()
    }
  }, [isOpen])

  const prepareCheckout = async () => {
    setPreparing(true)
    setError('')

    try {
      const response = await axios.post('/api/payment/prepare-checkout', {
        session_id: sessionId,
        user_email: userEmail
      })

      setCheckoutData(response.data)
      setMandateId(response.data.mandate_id)
    } catch (err: any) {
      console.error('Prepare checkout error:', err)
      setError(err.response?.data?.detail || 'Failed to prepare checkout')
    } finally {
      setPreparing(false)
    }
  }

  const confirmPayment = async () => {
    if (!checkoutData) return

    setLoading(true)
    setError('')

    try {
      // Step 1: Request passkey authentication
      const challengeResponse = await axios.post('/api/auth/challenge', {
        email: userEmail
      })

      const { challenge } = challengeResponse.data

      // Convert URL-safe base64 to standard base64 for atob()
      const base64Challenge = challenge.replace(/-/g, '+').replace(/_/g, '/').padEnd(
        challenge.length + (4 - (challenge.length % 4)) % 4, '='
      )

      // Step 2: Get passkey assertion
      const publicKeyCredentialRequestOptions: PublicKeyCredentialRequestOptions = {
        challenge: Uint8Array.from(atob(base64Challenge), c => c.charCodeAt(0)),
        rpId: window.location.hostname === 'localhost' ? 'localhost' : window.location.hostname,
        timeout: 60000,
        userVerification: "preferred"  // Changed from "required" to "preferred" for broader compatibility
      }

      const assertion = await navigator.credentials.get({
        publicKey: publicKeyCredentialRequestOptions
      }) as PublicKeyCredential

      if (!assertion) {
        throw new Error('Passkey authentication failed')
      }

      const assertionResponse = assertion.response as AuthenticatorAssertionResponse

      // Step 3: Verify passkey and confirm payment
      const verifyResponse = await axios.post('/api/auth/verify-passkey', {
        email: userEmail,
        challenge,
        credential_id: arrayBufferToUrlSafeBase64(assertion.rawId),
        client_data_json: arrayBufferToUrlSafeBase64(assertionResponse.clientDataJSON),
        authenticator_data: arrayBufferToUrlSafeBase64(assertionResponse.authenticatorData),
        signature: arrayBufferToUrlSafeBase64(assertionResponse.signature)
      })

      const { signature: userSignature } = verifyResponse.data

      // Step 4: Confirm checkout with signed mandate
      const confirmResponse = await axios.post('/api/payment/confirm-checkout', {
        mandate_id: mandateId,
        user_signature: userSignature,
        user_email: userEmail
      })

      const { status, receipt, otp_challenge } = confirmResponse.data

      if (status === 'success') {
        // Extract payment ID from receipt
        const paymentId = receipt?.payment_status?.merchant_confirmation_id ||
                         receipt?.merchant_confirmation_id ||
                         'CONFIRMED'
        setPaymentId(paymentId)
        setSuccess(true)

        // Notify parent component of successful payment
        if (onPaymentSuccess && checkoutData) {
          onPaymentSuccess(paymentId, checkoutData.cart_total, checkoutData.cart_items)
        }
      } else if (status === 'otp_required') {
        setOtpRequired(true)
        setOtpMessage(otp_challenge?.message || 'Additional verification required')
      } else {
        throw new Error('Payment failed')
      }

    } catch (err: any) {
      console.error('Payment error:', err)
      if (err.name === 'NotAllowedError') {
        setError('Passkey authentication was cancelled')
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail)
      } else {
        setError('Payment failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const verifyOTP = async () => {
    if (!otpCode || otpCode.length !== 6) {
      setError('Please enter a valid 6-digit OTP code')
      return
    }

    setLoading(true)
    setError('')

    try {
      const response = await axios.post('/api/payment/verify-otp', {
        mandate_id: mandateId,
        otp_code: otpCode,
        user_email: userEmail
      })

      const { status, receipt } = response.data

      if (status === 'success') {
        // Extract payment ID from receipt
        const paymentId = receipt?.payment_status?.merchant_confirmation_id ||
                         receipt?.merchant_confirmation_id ||
                         'CONFIRMED'
        setPaymentId(paymentId)
        setSuccess(true)
        setOtpRequired(false)

        // Notify parent component of successful payment
        if (onPaymentSuccess && checkoutData) {
          onPaymentSuccess(paymentId, checkoutData.cart_total, checkoutData.cart_items)
        }
      } else {
        throw new Error('OTP verification failed')
      }

    } catch (err: any) {
      console.error('OTP verification error:', err)
      setError(err.response?.data?.detail || 'Invalid OTP code')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setCheckoutData(null)
    setMandateId('')
    setPaymentId('')
    setError('')
    setSuccess(false)
    setOtpRequired(false)
    setOtpCode('')
    setOtpMessage('')
    setPreparing(true)
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50 animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto animate-slide-up">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <h2 className="text-xl font-bold text-gray-800 flex items-center">
            {success ? (
              <>
                <CheckCircle className="w-6 h-6 text-green-600 mr-2" />
                Payment Complete
              </>
            ) : otpRequired ? (
              <>
                <Shield className="w-6 h-6 text-blue-600 mr-2" />
                Verify OTP
              </>
            ) : (
              <>
                <ShoppingCart className="w-6 h-6 text-primary-600 mr-2" />
                Checkout
              </>
            )}
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {preparing ? (
            <div className="text-center py-12">
              <Loader className="w-12 h-12 text-primary-600 animate-spin mx-auto mb-4" />
              <p className="text-gray-600">Preparing checkout...</p>
            </div>
          ) : success ? (
            <div className="text-center py-8">
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle className="w-12 h-12 text-green-600" />
              </div>
              <h3 className="text-2xl font-bold text-gray-800 mb-2">Payment Successful!</h3>
              <p className="text-gray-600 mb-6">Your order has been confirmed</p>
              <div className="bg-gray-50 rounded-lg p-4 mb-6">
                <p className="text-sm text-gray-600 mb-1">Payment ID</p>
                <p className="text-sm font-mono text-gray-800">{paymentId}</p>
              </div>
              <button
                onClick={handleClose}
                className="btn-primary w-full"
              >
                Done
              </button>
            </div>
          ) : otpRequired ? (
            <div className="space-y-6">
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="flex items-start">
                  <Shield className="w-5 h-5 text-blue-600 mr-3 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-gray-800 mb-1">Additional Verification Required</p>
                    <p className="text-xs text-gray-600">{otpMessage}</p>
                  </div>
                </div>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
                  <AlertCircle className="w-5 h-5 text-red-600 mr-3 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              <div>
                <label htmlFor="otp" className="block text-sm font-medium text-gray-700 mb-2">
                  Enter 6-digit OTP Code
                </label>
                <input
                  type="text"
                  id="otp"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="input-field text-center text-2xl tracking-widest font-mono"
                  placeholder="000000"
                  maxLength={6}
                  disabled={loading}
                />
                <p className="text-xs text-gray-500 mt-2 text-center">
                  For demo: Use any 6-digit code
                </p>
              </div>

              <button
                onClick={verifyOTP}
                disabled={loading || otpCode.length !== 6}
                className="btn-primary w-full flex items-center justify-center space-x-2"
              >
                {loading ? (
                  <>
                    <Loader className="w-5 h-5 animate-spin" />
                    <span>Verifying...</span>
                  </>
                ) : (
                  <>
                    <Shield className="w-5 h-5" />
                    <span>Verify OTP</span>
                  </>
                )}
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Error Message */}
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
                  <AlertCircle className="w-5 h-5 text-red-600 mr-3 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              {/* Cart Items */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Order Summary</h3>
                <div className="space-y-3">
                  {checkoutData?.cart_items.map((item) => (
                    <div key={item.id} className="flex items-center space-x-3 py-2">
                      {item.image_url && (
                        <img
                          src={item.image_url}
                          alt={item.title}
                          className="w-16 h-16 object-cover rounded-lg border border-gray-200"
                          onError={(e) => {
                            // Hide image if it fails to load
                            e.currentTarget.style.display = 'none'
                          }}
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 truncate">{item.title}</p>
                        <p className="text-xs text-gray-500">SKU: {item.sku} • ID: {item.id}</p>
                        <p className="text-xs text-gray-500">Qty: {item.quantity}</p>
                      </div>
                      <p className="text-sm font-medium text-gray-800 whitespace-nowrap">
                        S${(item.price * item.quantity).toFixed(2)}
                      </p>
                    </div>
                  ))}
                </div>
                <div className="border-t border-gray-200 mt-4 pt-4 flex justify-between items-center">
                  <p className="text-base font-bold text-gray-800">Total</p>
                  <p className="text-xl font-bold text-primary-600">
                    S${checkoutData?.cart_total.toFixed(2)}
                  </p>
                </div>
              </div>

              {/* Payment Method */}
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Payment Method</h3>
                <div className="bg-gradient-to-r from-gray-800 to-gray-900 rounded-xl p-4 text-white">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <CreditCard className="w-6 h-6" />
                      <div>
                        <p className="text-sm font-medium">
                          •••• {checkoutData?.default_card.card_last_four}
                        </p>
                        <p className="text-xs text-gray-400 capitalize">
                          {checkoutData?.default_card.card_network}
                        </p>
                      </div>
                    </div>
                    <div className="w-12 h-8 bg-white rounded flex items-center justify-center">
                      <span className="text-xs font-bold text-gray-800">MC</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Passkey Info */}
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="flex items-start">
                  <Shield className="w-5 h-5 text-blue-600 mr-3 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-gray-800 mb-1">Secure with Passkey</p>
                    <p className="text-xs text-gray-600">
                      You'll be prompted to authenticate using your device's biometric authentication
                    </p>
                  </div>
                </div>
              </div>

              {/* Confirm Button */}
              <button
                onClick={confirmPayment}
                disabled={loading}
                className="btn-primary w-full flex items-center justify-center space-x-2"
              >
                {loading ? (
                  <>
                    <Loader className="w-5 h-5 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <Shield className="w-5 h-5" />
                    <span>Confirm Payment with Passkey</span>
                  </>
                )}
              </button>

              <p className="text-xs text-gray-500 text-center">
                Secured by AP2 Protocol • End-to-end encrypted
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default CheckoutPopup
