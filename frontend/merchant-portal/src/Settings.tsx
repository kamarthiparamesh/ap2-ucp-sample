import { useState, useEffect } from 'react'
import axios from 'axios'
import { ArrowLeft, Settings as SettingsIcon, Save, Shield, DollarSign, Info, AlertCircle } from 'lucide-react'

interface MerchantSettings {
  merchant_name: string
  merchant_id: string
  merchant_url: string
  otp_enabled: boolean
  otp_amount_threshold: number
}

interface SettingsProps {
  onBackToProducts: () => void
}

function Settings({ onBackToProducts }: SettingsProps) {
  const [settings, setSettings] = useState<MerchantSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [otpEnabled, setOtpEnabled] = useState(false)
  const [otpThreshold, setOtpThreshold] = useState('100.00')
  const [saveMessage, setSaveMessage] = useState('')

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      const response = await axios.get('/api/settings')
      setSettings(response.data)
      setOtpEnabled(response.data.otp_enabled)
      setOtpThreshold(response.data.otp_amount_threshold.toString())
    } catch (error) {
      console.error('Error fetching settings:', error)
      alert('Error loading settings')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setSaveMessage('')

    try {
      await axios.put('/api/settings', {
        otp_enabled: otpEnabled,
        otp_amount_threshold: parseFloat(otpThreshold)
      })

      setSaveMessage('Settings saved successfully! (In-memory only - will reset on server restart)')

      // Refresh settings
      await fetchSettings()

      // Clear message after 5 seconds
      setTimeout(() => setSaveMessage(''), 5000)
    } catch (error) {
      console.error('Error saving settings:', error)
      alert('Error saving settings')
    } finally {
      setSaving(false)
    }
  }

  const hasChanges = () => {
    if (!settings) return false
    return (
      settings.otp_enabled !== otpEnabled ||
      settings.otp_amount_threshold.toString() !== otpThreshold
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-500">Loading settings...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <button
                onClick={onBackToProducts}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-lg flex items-center justify-center">
                <SettingsIcon className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-800">Settings</h1>
                <p className="text-sm text-gray-500">Configure merchant preferences</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Merchant Info Card */}
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
            <Info className="w-5 h-5 mr-2 text-blue-600" />
            Merchant Information
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-600">Merchant Name</p>
              <p className="font-semibold text-gray-800">{settings?.merchant_name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Merchant ID</p>
              <p className="font-mono font-semibold text-gray-800">{settings?.merchant_id}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Merchant URL</p>
              <p className="font-mono text-sm text-gray-800">{settings?.merchant_url}</p>
            </div>
          </div>
        </div>

        {/* Payment Security Settings */}
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-2 flex items-center">
            <Shield className="w-5 h-5 mr-2 text-purple-600" />
            Payment Security
          </h2>
          <p className="text-sm text-gray-600 mb-6">
            Configure additional authentication requirements for payment processing
          </p>

          {/* Info Box */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-start space-x-3">
              <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-800">
                <p className="font-semibold mb-1">About Passkeys & OTP</p>
                <p className="mb-2">
                  This system uses <strong>passkeys (WebAuthn/FIDO2)</strong> for user authentication and payment authorization.
                  Passkeys are more secure than passwords and provide phishing-resistant multi-factor authentication.
                </p>
                <p>
                  <strong>OTP (One-Time Password)</strong> step-up authentication is <strong>disabled by default</strong> since
                  passkeys already provide strong security. Enable OTP only if you need additional verification for
                  high-value transactions or regulatory compliance.
                </p>
              </div>
            </div>
          </div>

          {/* OTP Toggle */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <div>
                <label className="text-sm font-medium text-gray-700 flex items-center">
                  Enable OTP Step-Up Authentication
                </label>
                <p className="text-xs text-gray-500 mt-1">
                  Require OTP verification for high-value transactions (in addition to passkey authentication)
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOtpEnabled(!otpEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 ${
                  otpEnabled ? 'bg-primary-600' : 'bg-gray-200'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    otpEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* OTP Threshold */}
          {otpEnabled && (
            <div className="border-t border-gray-200 pt-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                OTP Amount Threshold (SGD)
              </label>
              <p className="text-xs text-gray-500 mb-3">
                Transactions above this amount will require OTP verification
              </p>
              <div className="flex items-center space-x-2">
                <DollarSign className="w-5 h-5 text-gray-400" />
                <input
                  type="number"
                  step="0.01"
                  value={otpThreshold}
                  onChange={(e) => setOtpThreshold(e.target.value)}
                  className="input-field max-w-xs"
                  placeholder="100.00"
                />
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Example: If set to $100, transactions of $100.01 or more will require OTP
              </p>
            </div>
          )}
        </div>

        {/* Warning Box */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-yellow-800">
              <p className="font-semibold mb-1">Important Note</p>
              <p>
                Settings changes are <strong>in-memory only</strong> and will reset when the server restarts.
                To make permanent changes, update the <code className="bg-yellow-100 px-1 rounded">ENABLE_OTP_CHALLENGE</code> and{' '}
                <code className="bg-yellow-100 px-1 rounded">OTP_AMOUNT_THRESHOLD</code> values in the{' '}
                <code className="bg-yellow-100 px-1 rounded">.env</code> file.
              </p>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex items-center justify-between">
          <button
            onClick={onBackToProducts}
            className="btn-secondary flex items-center space-x-2"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back</span>
          </button>

          <div className="flex items-center space-x-4">
            {saveMessage && (
              <p className="text-sm text-green-600 font-medium">
                {saveMessage}
              </p>
            )}
            <button
              onClick={handleSave}
              disabled={!hasChanges() || saving}
              className={`btn-primary flex items-center space-x-2 ${
                (!hasChanges() || saving) && 'opacity-50 cursor-not-allowed'
              }`}
            >
              <Save className="w-4 h-4" />
              <span>{saving ? 'Saving...' : 'Save Changes'}</span>
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

export default Settings
