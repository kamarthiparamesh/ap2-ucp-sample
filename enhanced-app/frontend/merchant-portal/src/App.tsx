import { useState, useEffect } from 'react'
import axios from 'axios'
import { Plus, Edit2, Trash2, Save, X, Store, MessageSquare, DollarSign, BarChart3 } from 'lucide-react'
import Dashboard from './Dashboard'

interface Product {
  id: string
  sku: string
  name: string
  description: string | null
  price: number
  currency: string
  category: string | null
  brand: string | null
  image_url: string | null
  availability: string
  condition: string
  is_active: boolean
  created_at: string
  updated_at: string
}

interface ProductFormData {
  sku: string
  name: string
  description: string
  price: string
  currency: string
  category: string
  brand: string
  image_url: string
}

function App() {
  const [currentPage, setCurrentPage] = useState<'products' | 'dashboard'>('products')
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [formData, setFormData] = useState<ProductFormData>({
    sku: '',
    name: '',
    description: '',
    price: '',
    currency: 'SGD',
    category: '',
    brand: '',
    image_url: ''
  })

  useEffect(() => {
    fetchProducts()
  }, [])

  const fetchProducts = async () => {
    try {
      const response = await axios.get('/api/products')
      setProducts(response.data)
    } catch (error) {
      console.error('Error fetching products:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const imageUrls = formData.image_url
      ? formData.image_url.split(',').map(url => url.trim())
      : []

    const productData = {
      ...formData,
      price: parseFloat(formData.price),
      image_url: imageUrls
    }

    try {
      if (editingId) {
        await axios.put(`/api/products/${editingId}`, productData)
      } else {
        await axios.post('/api/products', productData)
      }

      resetForm()
      fetchProducts()
    } catch (error) {
      console.error('Error saving product:', error)
      alert('Error saving product. Please check the form and try again.')
    }
  }

  const handleEdit = (product: Product) => {
    setEditingId(product.id)
    setShowAddForm(true)

    const images = product.image_url
      ? JSON.parse(product.image_url).join(', ')
      : ''

    setFormData({
      sku: product.sku,
      name: product.name,
      description: product.description || '',
      price: product.price.toString(),
      currency: product.currency,
      category: product.category || '',
      brand: product.brand || '',
      image_url: images
    })
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this product?')) return

    try {
      await axios.delete(`/api/products/${id}`)
      fetchProducts()
    } catch (error) {
      console.error('Error deleting product:', error)
      alert('Error deleting product')
    }
  }

  const resetForm = () => {
    setFormData({
      sku: '',
      name: '',
      description: '',
      price: '',
      currency: 'SGD',
      category: '',
      brand: '',
      image_url: ''
    })
    setEditingId(null)
    setShowAddForm(false)
  }

  // If dashboard page is active, render it
  if (currentPage === 'dashboard') {
    return <Dashboard onBackToProducts={() => setCurrentPage('products')} />
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Store className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-800">Merchant Portal</h1>
                <p className="text-sm text-gray-500">Manage your products and pricing</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setCurrentPage('dashboard')}
                className="flex items-center space-x-2 text-primary-600 hover:text-primary-700 transition-colors font-medium"
              >
                <BarChart3 className="w-5 h-5" />
                <span>Dashboard</span>
              </button>
              <a
                href="https://chat.abhinava.xyz"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center space-x-2 text-primary-600 hover:text-primary-700 transition-colors font-medium"
              >
                <MessageSquare className="w-5 h-5" />
                <span>Chat Interface</span>
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Total Products</p>
                <p className="text-3xl font-bold text-gray-800">{products.length}</p>
              </div>
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <Store className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Active Products</p>
                <p className="text-3xl font-bold text-gray-800">
                  {products.filter(p => p.is_active).length}
                </p>
              </div>
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">Average Price</p>
                <p className="text-3xl font-bold text-gray-800">
                  S${products.length > 0
                    ? (products.reduce((sum, p) => sum + p.price, 0) / products.length).toFixed(2)
                    : '0.00'
                  }
                </p>
              </div>
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-purple-600" />
              </div>
            </div>
          </div>
        </div>

        {/* Add Product Button */}
        <div className="mb-6">
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="btn-primary flex items-center space-x-2"
          >
            {showAddForm ? (
              <>
                <X className="w-5 h-5" />
                <span>Cancel</span>
              </>
            ) : (
              <>
                <Plus className="w-5 h-5" />
                <span>Add New Product</span>
              </>
            )}
          </button>
        </div>

        {/* Add/Edit Form */}
        {showAddForm && (
          <div className="card mb-8 animate-slide-up">
            <h2 className="text-xl font-bold text-gray-800 mb-6">
              {editingId ? 'Edit Product' : 'Add New Product'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    SKU <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    className="input-field"
                    value={formData.sku}
                    onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                    placeholder="e.g., PROD-001"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Product Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    className="input-field"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., Chocolate Chip Cookies"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Price <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    className="input-field"
                    value={formData.price}
                    onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                    placeholder="9.99"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Category
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    placeholder="e.g., Snacks/Cookies"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Brand
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    value={formData.brand}
                    onChange={(e) => setFormData({ ...formData, brand: e.target.value })}
                    placeholder="e.g., BrandName"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Currency
                  </label>
                  <select
                    className="input-field"
                    value={formData.currency}
                    onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                  >
                    <option value="SGD">SGD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                    <option value="USD">USD</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Description
                </label>
                <textarea
                  className="input-field"
                  rows={3}
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Product description..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Image URLs (comma-separated)
                </label>
                <input
                  type="text"
                  className="input-field"
                  value={formData.image_url}
                  onChange={(e) => setFormData({ ...formData, image_url: e.target.value })}
                  placeholder="https://example.com/image1.jpg, https://example.com/image2.jpg"
                />
              </div>

              <div className="flex space-x-4">
                <button type="submit" className="btn-primary flex items-center space-x-2">
                  <Save className="w-4 h-4" />
                  <span>{editingId ? 'Update Product' : 'Create Product'}</span>
                </button>
                <button
                  type="button"
                  onClick={resetForm}
                  className="btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Products Table */}
        <div className="card">
          <h2 className="text-xl font-bold text-gray-800 mb-6">Products</h2>

          {loading ? (
            <div className="text-center py-12">
              <div className="inline-block w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
              <p className="mt-4 text-gray-600">Loading products...</p>
            </div>
          ) : products.length === 0 ? (
            <div className="text-center py-12">
              <Store className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-600">No products found. Add your first product!</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b-2 border-gray-200">
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">SKU</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">Name</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">Category</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">Brand</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">Price</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">Status</th>
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((product) => (
                    <tr key={product.id} className="table-row">
                      <td className="py-3 px-4">
                        <span className="font-mono text-sm text-gray-600">{product.sku}</span>
                      </td>
                      <td className="py-3 px-4">
                        <div>
                          <p className="font-medium text-gray-800">{product.name}</p>
                          {product.description && (
                            <p className="text-sm text-gray-500 truncate max-w-xs">
                              {product.description}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-gray-600">{product.category || '-'}</td>
                      <td className="py-3 px-4 text-gray-600">{product.brand || '-'}</td>
                      <td className="py-3 px-4">
                        <span className="font-semibold text-gray-800">
                          {product.currency} {product.price.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                          product.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {product.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex justify-end space-x-2">
                          <button
                            onClick={() => handleEdit(product)}
                            className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                            title="Edit"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(product.id)}
                            className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
