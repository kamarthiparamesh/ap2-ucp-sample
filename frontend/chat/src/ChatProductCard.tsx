import { Plus, Check } from 'lucide-react'
import { useState } from 'react'

interface Product {
  id: string
  sku: string
  name: string
  description: string
  price: number
  image_url?: string
}

interface ChatProductCardProps {
  product: Product
  isInCart: boolean
  onAddToCart: (productId: string, productName: string) => Promise<void>
}

export function ChatProductCard({ product, isInCart, onAddToCart }: ChatProductCardProps) {
  const [imageError, setImageError] = useState(false)
  const [isAdding, setIsAdding] = useState(false)

  const handleAddToCart = async () => {
    setIsAdding(true)
    await onAddToCart(product.id, product.name)
    setTimeout(() => setIsAdding(false), 300)
  }

  // Parse image URL if it's a JSON array string
  let imageUrl = product.image_url || ''
  if (typeof imageUrl === 'string' && imageUrl.startsWith('[')) {
    try {
      const urls = JSON.parse(imageUrl)
      imageUrl = urls[0] || ''
    } catch {
      imageUrl = ''
    }
  }

  return (
    <div className="chat-product-card group">
      {/* Product Image */}
      <div className="relative overflow-hidden rounded-lg bg-gray-100 aspect-square">
        {!imageError && imageUrl ? (
          <img
            src={imageUrl}
            alt={product.name}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110"
            onError={() => setImageError(true)}
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-100 to-gray-200">
            <span className="text-4xl">🍪</span>
          </div>
        )}

        {/* Price Badge */}
        <div className="absolute top-2 right-2 bg-white/95 backdrop-blur-sm px-2 py-1 rounded-full shadow-md">
          <span className="text-sm font-bold text-primary-600">S${product.price.toFixed(2)}</span>
        </div>
      </div>

      {/* Product Info */}
      <div className="p-3 flex-1 flex flex-col">
        <h4 className="text-sm font-semibold text-gray-800 mb-1 line-clamp-1">{product.name}</h4>
        <p className="text-xs text-gray-500 mb-2">SKU: {product.sku}</p>
        <p className="text-xs text-gray-600 mb-3 line-clamp-2 flex-1">{product.description}</p>

        {/* Add to Cart Button */}
        <button
          onClick={handleAddToCart}
          disabled={isInCart || isAdding}
          className={`
            w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg
            font-medium text-sm transition-all duration-200
            ${
              isInCart
                ? 'bg-green-500 text-white cursor-default'
                : 'bg-primary-600 text-white hover:bg-primary-700 active:scale-95'
            }
            ${isAdding ? 'opacity-75' : ''}
            disabled:opacity-75 disabled:cursor-not-allowed
          `}
        >
          {isAdding ? (
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : isInCart ? (
            <>
              <Check className="w-4 h-4" />
              <span>In Cart</span>
            </>
          ) : (
            <>
              <Plus className="w-4 h-4" />
              <span>Add</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}

interface ChatProductGridProps {
  products: Product[]
  cartItems: Set<string>
  onAddToCart: (productId: string, productName: string) => Promise<void>
}

export function ChatProductGrid({ products, cartItems, onAddToCart }: ChatProductGridProps) {
  return (
    <div className="chat-product-grid">
      {products.map((product) => (
        <ChatProductCard
          key={product.id}
          product={product}
          isInCart={cartItems.has(product.id)}
          onAddToCart={onAddToCart}
        />
      ))}
    </div>
  )
}
