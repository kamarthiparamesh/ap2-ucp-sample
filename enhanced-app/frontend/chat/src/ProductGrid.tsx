import ProductCard from './ProductCard'

interface Product {
  id: string
  sku: string
  title: string
  description: string
  price: number
  imageUrl?: string
}

interface ProductGridProps {
  products: Product[]
  cartItems: Set<string>
  onAddToCart: (id: string, title: string) => void
}

function ProductGrid({ products, cartItems, onAddToCart }: ProductGridProps) {
  if (products.length === 0) {
    return null
  }

  return (
    <div className="my-6 animate-slide-up">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-800 flex items-center">
          <span className="mr-2">🛍️</span>
          Available Products
        </h2>
        <span className="text-sm text-gray-500">
          {products.length} {products.length === 1 ? 'item' : 'items'}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {products.map((product) => (
          <ProductCard
            key={product.id}
            id={product.id}
            sku={product.sku}
            title={product.title}
            description={product.description}
            price={product.price}
            imageUrl={product.imageUrl}
            isInCart={cartItems.has(product.id)}
            onAddToCart={onAddToCart}
          />
        ))}
      </div>
    </div>
  )
}

export default ProductGrid
