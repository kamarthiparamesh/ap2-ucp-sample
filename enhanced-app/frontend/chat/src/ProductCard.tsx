import { useState } from 'react'
import { Plus, Check, ShoppingCart } from 'lucide-react'

interface ProductCardProps {
  id: string
  sku: string
  title: string
  description: string
  price: number
  imageUrl?: string
  isInCart: boolean
  onAddToCart: (id: string, title: string) => void
}

function ProductCard({ id, sku, title, description, price, imageUrl, isInCart, onAddToCart }: ProductCardProps) {
  const [imageError, setImageError] = useState(false)
  const [isAdding, setIsAdding] = useState(false)

  const handleAddToCart = async () => {
    setIsAdding(true)
    await onAddToCart(id, title)
    setTimeout(() => setIsAdding(false), 300)
  }

  return (
    <div className="product-card group">
      {/* Product Image */}
      <div className="relative overflow-hidden rounded-t-xl bg-gray-100 aspect-square">
        {imageUrl && !imageError ? (
          <img
            src={imageUrl}
            alt={title}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-gray-100 to-gray-200">
            <ShoppingCart className="w-16 h-16 text-gray-400" />
          </div>
        )}

        {/* Price Badge */}
        <div className="absolute top-3 right-3 bg-white/95 backdrop-blur-sm px-3 py-1.5 rounded-full shadow-lg">
          <span className="text-lg font-bold text-primary-600">S${price.toFixed(2)}</span>
        </div>
      </div>

      {/* Product Info */}
      <div className="p-4 flex-1 flex flex-col">
        <h3 className="text-lg font-semibold text-gray-800 mb-1 line-clamp-2 group-hover:text-primary-600 transition-colors">
          {title}
        </h3>

        <p className="text-xs text-gray-500 mb-2">SKU: {sku}</p>

        <p className="text-sm text-gray-600 mb-4 line-clamp-2 flex-1">
          {description}
        </p>

        {/* Add to Cart Button */}
        <button
          onClick={handleAddToCart}
          disabled={isInCart}
          className={`w-full flex items-center justify-center space-x-2 py-3 rounded-lg font-medium transition-all duration-200 ${
            isInCart
              ? 'bg-green-500 text-white cursor-default'
              : 'bg-primary-600 hover:bg-primary-700 text-white hover:shadow-lg active:scale-95'
          }`}
        >
          {isAdding ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : isInCart ? (
            <>
              <Check className="w-5 h-5" />
              <span>In Cart</span>
            </>
          ) : (
            <>
              <Plus className="w-5 h-5" />
              <span>Add to Cart</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}

export default ProductCard
