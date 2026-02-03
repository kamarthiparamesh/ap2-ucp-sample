import { useState, useEffect } from 'react'
import axios from 'axios'
import { Plus, Edit2, Trash2, Save, X, Tag, ArrowLeft, Percent, DollarSign, Calendar, Users, CheckCircle, XCircle } from 'lucide-react'

interface Promocode {
  id: string
  code: string
  description: string | null
  discount_type: 'percentage' | 'fixed_amount'
  discount_value: number
  currency: string
  min_purchase_amount: number | null
  max_discount_amount: number | null
  usage_limit: number | null
  usage_count: number
  valid_from: string | null
  valid_until: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

interface PromocodeFormData {
  code: string
  description: string
  discount_type: 'percentage' | 'fixed_amount'
  discount_value: string
  min_purchase_amount: string
  max_discount_amount: string
  usage_limit: string
  valid_from: string
  valid_until: string
}

interface PromocodesProps {
  onBackToProducts: () => void
}

function Promocodes({ onBackToProducts }: PromocodesProps) {
  const [promocodes, setPromocodes] = useState<Promocode[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [formData, setFormData] = useState<PromocodeFormData>({
    code: '',
    description: '',
    discount_type: 'percentage',
    discount_value: '',
    min_purchase_amount: '',
    max_discount_amount: '',
    usage_limit: '',
    valid_from: '',
    valid_until: ''
  })

  useEffect(() => {
    fetchPromocodes()
  }, [])

  const fetchPromocodes = async () => {
    try {
      const response = await axios.get('/api/promocodes')
      setPromocodes(response.data)
    } catch (error) {
      console.error('Error fetching promocodes:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const promocodeData = {
      code: formData.code.toUpperCase(),
      description: formData.description || null,
      discount_type: formData.discount_type,
      discount_value: parseFloat(formData.discount_value),
      currency: 'SGD',
      min_purchase_amount: formData.min_purchase_amount ? parseFloat(formData.min_purchase_amount) : null,
      max_discount_amount: formData.max_discount_amount ? parseFloat(formData.max_discount_amount) : null,
      usage_limit: formData.usage_limit ? parseInt(formData.usage_limit) : null,
      valid_from: formData.valid_from ? new Date(formData.valid_from).toISOString() : null,
      valid_until: formData.valid_until ? new Date(formData.valid_until).toISOString() : null
    }

    try {
      if (editingId) {
        await axios.put(`/api/promocodes/${editingId}`, promocodeData)
      } else {
        await axios.post('/api/promocodes', promocodeData)
      }

      resetForm()
      fetchPromocodes()
    } catch (error: any) {
      console.error('Error saving promocode:', error)
      alert(error.response?.data?.detail || 'Error saving promocode. Please check the form and try again.')
    }
  }

  const handleEdit = (promocode: Promocode) => {
    setEditingId(promocode.id)
    setShowAddForm(true)

    setFormData({
      code: promocode.code,
      description: promocode.description || '',
      discount_type: promocode.discount_type,
      discount_value: promocode.discount_value.toString(),
      min_purchase_amount: promocode.min_purchase_amount?.toString() || '',
      max_discount_amount: promocode.max_discount_amount?.toString() || '',
      usage_limit: promocode.usage_limit?.toString() || '',
      valid_from: promocode.valid_from ? promocode.valid_from.split('T')[0] : '',
      valid_until: promocode.valid_until ? promocode.valid_until.split('T')[0] : ''
    })
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this promocode?')) return

    try {
      await axios.delete(`/api/promocodes/${id}`)
      fetchPromocodes()
    } catch (error) {
      console.error('Error deleting promocode:', error)
      alert('Error deleting promocode')
    }
  }

  const resetForm = () => {
    setFormData({
      code: '',
      description: '',
      discount_type: 'percentage',
      discount_value: '',
      min_purchase_amount: '',
      max_discount_amount: '',
      usage_limit: '',
      valid_from: '',
      valid_until: ''
    })
    setEditingId(null)
    setShowAddForm(false)
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'No expiry'
    return new Date(dateString).toLocaleDateString()
  }

  const isExpired = (dateString: string | null) => {
    if (!dateString) return false
    return new Date(dateString) < new Date()
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <button
                onClick={onBackToProducts}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg flex items-center justify-center">
                <Tag className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-800">Promocodes</h1>
                <p className="text-sm text-gray-500">Manage discount codes and vouchers</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Total Codes</p>
                <p className="text-3xl font-bold text-gray-800">{promocodes.length}</p>
              </div>
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <Tag className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Active Codes</p>
                <p className="text-3xl font-bold text-gray-800">
                  {promocodes.filter(p => p.is_active && !isExpired(p.valid_until)).length}
                </p>
              </div>
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <CheckCircle className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Total Uses</p>
                <p className="text-3xl font-bold text-gray-800">
                  {promocodes.reduce((sum, p) => sum + p.usage_count, 0)}
                </p>
              </div>
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <Users className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Expired</p>
                <p className="text-3xl font-bold text-gray-800">
                  {promocodes.filter(p => isExpired(p.valid_until)).length}
                </p>
              </div>
              <div className="w-12 h-12 bg-red-100 rounded-lg flex items-center justify-center">
                <XCircle className="w-6 h-6 text-red-600" />
              </div>
            </div>
          </div>
        </div>

        {/* Add Button */}
        <div className="mb-6">
          <button
            onClick={() => setShowAddForm(true)}
            className="btn-primary flex items-center space-x-2"
          >
            <Plus className="w-5 h-5" />
            <span>Add New Promocode</span>
          </button>
        </div>

        {/* Add/Edit Form */}
        {showAddForm && (
          <div className="card mb-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-800">
                {editingId ? 'Edit Promocode' : 'Add New Promocode'}
              </h2>
              <button
                onClick={resetForm}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-600" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Code */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Code *
                </label>
                <input
                  type="text"
                  required
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                  className="input-field"
                  placeholder="SAVE10"
                  disabled={editingId !== null}
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Description
                </label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="input-field"
                  placeholder="10% off your order"
                />
              </div>

              {/* Discount Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Discount Type *
                </label>
                <select
                  required
                  value={formData.discount_type}
                  onChange={(e) => setFormData({ ...formData, discount_type: e.target.value as 'percentage' | 'fixed_amount' })}
                  className="input-field"
                >
                  <option value="percentage">Percentage</option>
                  <option value="fixed_amount">Fixed Amount</option>
                </select>
              </div>

              {/* Discount Value */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Discount Value * {formData.discount_type === 'percentage' ? '(%)' : '(SGD)'}
                </label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={formData.discount_value}
                  onChange={(e) => setFormData({ ...formData, discount_value: e.target.value })}
                  className="input-field"
                  placeholder={formData.discount_type === 'percentage' ? '10' : '5.00'}
                />
              </div>

              {/* Min Purchase Amount */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Min Purchase Amount (SGD)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.min_purchase_amount}
                  onChange={(e) => setFormData({ ...formData, min_purchase_amount: e.target.value })}
                  className="input-field"
                  placeholder="20.00"
                />
              </div>

              {/* Max Discount Amount */}
              {formData.discount_type === 'percentage' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Max Discount Cap (SGD)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.max_discount_amount}
                    onChange={(e) => setFormData({ ...formData, max_discount_amount: e.target.value })}
                    className="input-field"
                    placeholder="10.00"
                  />
                </div>
              )}

              {/* Usage Limit */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Usage Limit
                </label>
                <input
                  type="number"
                  value={formData.usage_limit}
                  onChange={(e) => setFormData({ ...formData, usage_limit: e.target.value })}
                  className="input-field"
                  placeholder="100 (leave empty for unlimited)"
                />
              </div>

              {/* Valid From */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Valid From
                </label>
                <input
                  type="date"
                  value={formData.valid_from}
                  onChange={(e) => setFormData({ ...formData, valid_from: e.target.value })}
                  className="input-field"
                />
              </div>

              {/* Valid Until */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Valid Until
                </label>
                <input
                  type="date"
                  value={formData.valid_until}
                  onChange={(e) => setFormData({ ...formData, valid_until: e.target.value })}
                  className="input-field"
                />
              </div>

              {/* Submit Buttons */}
              <div className="md:col-span-2 flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={resetForm}
                  className="btn-secondary flex items-center space-x-2"
                >
                  <X className="w-4 h-4" />
                  <span>Cancel</span>
                </button>
                <button
                  type="submit"
                  className="btn-primary flex items-center space-x-2"
                >
                  <Save className="w-4 h-4" />
                  <span>{editingId ? 'Update' : 'Create'} Promocode</span>
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Promocodes List */}
        {loading ? (
          <div className="card text-center py-12">
            <div className="w-16 h-16 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-gray-500">Loading promocodes...</p>
          </div>
        ) : promocodes.length === 0 ? (
          <div className="card text-center py-12">
            <Tag className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-4">No promocodes yet</p>
            <button
              onClick={() => setShowAddForm(true)}
              className="btn-primary inline-flex items-center space-x-2"
            >
              <Plus className="w-5 h-5" />
              <span>Add Your First Promocode</span>
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {promocodes.map((promo) => (
              <div key={promo.id} className="card hover:shadow-lg transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <div className={`px-4 py-2 rounded-lg font-mono font-bold text-lg ${
                        promo.is_active && !isExpired(promo.valid_until)
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-500'
                      }`}>
                        {promo.code}
                      </div>
                      {!promo.is_active && (
                        <span className="px-3 py-1 bg-gray-100 text-gray-600 text-sm rounded-full">
                          Inactive
                        </span>
                      )}
                      {isExpired(promo.valid_until) && (
                        <span className="px-3 py-1 bg-red-100 text-red-600 text-sm rounded-full">
                          Expired
                        </span>
                      )}
                    </div>

                    <p className="text-gray-700 mb-3">{promo.description || 'No description'}</p>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Discount</p>
                        <p className="font-semibold text-gray-800 flex items-center">
                          {promo.discount_type === 'percentage' ? (
                            <>
                              <Percent className="w-4 h-4 mr-1" />
                              {promo.discount_value}%
                            </>
                          ) : (
                            <>
                              <DollarSign className="w-4 h-4 mr-1" />
                              ${promo.discount_value}
                            </>
                          )}
                        </p>
                      </div>

                      <div>
                        <p className="text-gray-500">Usage</p>
                        <p className="font-semibold text-gray-800">
                          {promo.usage_count} / {promo.usage_limit || '∞'}
                        </p>
                      </div>

                      <div>
                        <p className="text-gray-500">Expires</p>
                        <p className="font-semibold text-gray-800 flex items-center">
                          <Calendar className="w-4 h-4 mr-1" />
                          {formatDate(promo.valid_until)}
                        </p>
                      </div>

                      <div>
                        <p className="text-gray-500">Min Purchase</p>
                        <p className="font-semibold text-gray-800">
                          {promo.min_purchase_amount ? `$${promo.min_purchase_amount}` : 'None'}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 ml-4">
                    <button
                      onClick={() => handleEdit(promo)}
                      className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                      title="Edit"
                    >
                      <Edit2 className="w-5 h-5 text-gray-600" />
                    </button>
                    <button
                      onClick={() => handleDelete(promo.id)}
                      className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-5 h-5 text-red-600" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

export default Promocodes
