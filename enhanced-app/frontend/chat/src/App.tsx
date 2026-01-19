import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { Send, ShoppingCart, Sparkles, Bot, User, UserPlus, Grid3x3, LogOut } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import RegisterPage from './RegisterPage'
import CheckoutPopup from './CheckoutPopup'
import ProductGrid from './ProductGrid'
import { ChatProductGrid } from './ChatProductCard'

interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  timestamp: Date
  products?: Product[]
}

interface Product {
  id: string
  sku: string
  name: string
  description: string
  price: number
  image_url?: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId] = useState(`session-${Date.now()}`)
  const [showRegister, setShowRegister] = useState(false)
  const [showCheckout, setShowCheckout] = useState(false)
  const [userEmail, setUserEmail] = useState('')
  const [isRegistered, setIsRegistered] = useState(false)
  const [showProductGrid, setShowProductGrid] = useState(false)
  const [products, setProducts] = useState<Product[]>([])
  const [cartItems, setCartItems] = useState<Set<string>>(new Set())
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    // Check if user is registered (check localStorage)
    const savedEmail = localStorage.getItem('userEmail')
    if (savedEmail) {
      setUserEmail(savedEmail)
      setIsRegistered(true)
    }

    // Add welcome message
    setMessages([
      {
        id: '1',
        content: isRegistered
          ? `👋 Welcome back! I'm your AI Shopping Assistant. Ready to help you shop. What are you looking for today?`
          : "👋 Hello! I'm your AI Shopping Assistant powered by Ollama. I can help you find products, manage your cart, and complete your purchase. To use secure checkout with AP2 payment, please register first!",
        role: 'assistant',
        timestamp: new Date()
      }
    ])
  }, [])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    // Check if user is trying to checkout
    const checkoutKeywords = ['checkout', 'pay', 'purchase', 'buy now', 'complete order']
    const isCheckoutIntent = checkoutKeywords.some(keyword => input.toLowerCase().includes(keyword))

    if (isCheckoutIntent && !isRegistered) {
      const errorMessage: Message = {
        id: Date.now().toString(),
        content: "To complete checkout, please register first. Click the 'Register' button in the header to create your account with secure passkey authentication.",
        role: 'assistant',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
      return
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input,
      role: 'user',
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await axios.post('/api/chat', {
        message: input,
        session_id: sessionId
      })

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: response.data.response,
        role: 'assistant',
        timestamp: new Date()
      }

      // Include product data if present in the response
      if (response.data.products && Array.isArray(response.data.products)) {
        assistantMessage.products = response.data.products.map((p: any) => ({
          id: p.id,
          sku: p.sku || p.id,
          name: p.name,
          description: p.description || '',
          price: p.price,
          image_url: p.image_url
        }))

        // Update cart items set with product IDs
        const currentCart = new Set(cartItems)
        assistantMessage.products.forEach(p => {
          // Check if product is mentioned in cart context
          if (response.data.response.toLowerCase().includes('in cart') ||
              response.data.response.toLowerCase().includes('added')) {
            currentCart.add(p.id)
          }
        })
        setCartItems(currentCart)
      }

      setMessages(prev => [...prev, assistantMessage])

      // If checkout intent detected and user is registered, open checkout popup
      if (isCheckoutIntent && isRegistered) {
        setTimeout(() => setShowCheckout(true), 500)
      }
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: "I'm sorry, I encountered an error. Please try again.",
        role: 'assistant',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleRegistrationComplete = (email: string) => {
    setUserEmail(email)
    setIsRegistered(true)
    localStorage.setItem('userEmail', email)
    setShowRegister(false)

    // Add success message
    const successMessage: Message = {
      id: Date.now().toString(),
      content: `Great! Your account has been set up successfully. You can now browse products and use secure checkout with your passkey. What would you like to shop for?`,
      role: 'assistant',
      timestamp: new Date()
    }
    setMessages(prev => [...prev, successMessage])
  }

  const handlePaymentSuccess = (paymentId: string, total: number, items: any[]) => {
    // Create a detailed confirmation message
    const itemsList = items.map(item => `• ${item.title} (x${item.quantity}) - S$${(item.price * item.quantity).toFixed(2)}`).join('\n')

    const confirmationMessage: Message = {
      id: Date.now().toString(),
      content: `## 🎉 Payment Successful!\n\n**Order Confirmed**\n\nYour payment has been processed successfully!\n\n**Order Details:**\n${itemsList}\n\n**Total Amount:** S$${total.toFixed(2)}\n\n**Payment ID:** ${paymentId}\n\nThank you for your purchase! Your order will be processed shortly.`,
      role: 'assistant',
      timestamp: new Date()
    }
    setMessages(prev => [...prev, confirmationMessage])

    // Clear cart items after successful payment
    setCartItems(new Set())
  }

  const handleLogout = () => {
    if (!confirm('Are you sure you want to logout?')) {
      return
    }

    // Clear user data
    localStorage.removeItem('userEmail')
    setUserEmail('')
    setIsRegistered(false)
    setCartItems(new Set())

    // Reset messages with welcome message
    setMessages([
      {
        id: '1',
        content: "👋 Hello! I'm your AI Shopping Assistant powered by Ollama. I can help you find products, manage your cart, and complete your purchase. To use secure checkout with AP2 payment, please register first!",
        role: 'assistant',
        timestamp: new Date()
      }
    ])
  }

  const fetchProducts = async (query?: string) => {
    try {
      const params = query ? `?query=${encodeURIComponent(query)}` : ''
      const response = await axios.get(`/api/products${params}`)
      const fetchedProducts = response.data.products.map((p: any) => ({
        id: p.id,
        sku: p.sku || p.id,
        name: p.name,
        description: p.description || '',
        price: p.price,
        image_url: p.image_url
      }))
      setProducts(fetchedProducts)
      setShowProductGrid(true)
    } catch (error) {
      console.error('Error fetching products:', error)
    }
  }

  const handleAddToCartFromGrid = async (productId: string, productName: string) => {
    // Send message to chat backend to add to cart
    const addMessage = `add ${productName} to cart`
    const userMessage: Message = {
      id: Date.now().toString(),
      content: addMessage,
      role: 'user',
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMessage])

    try {
      const response = await axios.post('/api/chat', {
        message: addMessage,
        session_id: sessionId
      })

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: response.data.response,
        role: 'assistant',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, assistantMessage])

      // Update cart items
      setCartItems(prev => new Set(prev).add(productId))
    } catch (error) {
      console.error('Error adding to cart:', error)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  if (showRegister) {
    return (
      <RegisterPage
        onRegistrationComplete={handleRegistrationComplete}
        onBackToChat={() => setShowRegister(false)}
      />
    )
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-800">AI Shopping Assistant</h1>
              <p className="text-sm text-gray-500">
                {isRegistered ? `Logged in as ${userEmail}` : 'Powered by Ollama'}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <button
              onClick={() => fetchProducts()}
              className="flex items-center space-x-2 text-gray-700 hover:text-primary-600 transition-colors font-medium"
            >
              <Grid3x3 className="w-5 h-5" />
              <span>Browse Products</span>
            </button>
            {!isRegistered ? (
              <button
                onClick={() => setShowRegister(true)}
                className="flex items-center space-x-2 text-primary-600 hover:text-primary-700 transition-colors font-medium"
              >
                <UserPlus className="w-5 h-5" />
                <span>Register</span>
              </button>
            ) : (
              <button
                onClick={handleLogout}
                className="flex items-center space-x-2 text-red-600 hover:text-red-700 transition-colors font-medium"
              >
                <LogOut className="w-5 h-5" />
                <span>Logout</span>
              </button>
            )}
            <a
              href="https://app.abhinava.xyz"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center space-x-2 text-gray-600 hover:text-gray-700 transition-colors"
            >
              <ShoppingCart className="w-5 h-5" />
              <span className="font-medium">Merchant Portal</span>
            </a>
          </div>
        </div>
      </header>

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-6xl mx-auto space-y-6">
          {/* Product Grid */}
          {showProductGrid && (
            <ProductGrid
              products={products.map(p => ({
                id: p.id,
                sku: p.sku,
                title: p.name,
                description: p.description,
                price: p.price,
                imageUrl: p.image_url
              }))}
              cartItems={cartItems}
              onAddToCart={handleAddToCartFromGrid}
            />
          )}

          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex items-start space-x-3 animate-slide-up ${
                message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''
              }`}
            >
              {/* Avatar */}
              <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
                message.role === 'user'
                  ? 'bg-primary-600'
                  : 'bg-gradient-to-br from-purple-500 to-pink-500'
              }`}>
                {message.role === 'user' ? (
                  <User className="w-5 h-5 text-white" />
                ) : (
                  <Bot className="w-5 h-5 text-white" />
                )}
              </div>

              {/* Message Bubble */}
              <div className={`flex-1 ${message.role === 'user' ? 'items-end' : 'items-start'} flex flex-col`}>
                <div className={`chat-bubble ${
                  message.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'
                }`}>
                  {message.role === 'assistant' ? (
                    <div className="prose prose-sm max-w-none prose-headings:mt-3 prose-headings:mb-2 prose-p:my-1">
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  )}
                </div>

                {/* Product Cards in Chat */}
                {message.products && message.products.length > 0 && (
                  <div className="mt-4 w-full">
                    <ChatProductGrid
                      products={message.products}
                      cartItems={cartItems}
                      onAddToCart={handleAddToCartFromGrid}
                    />
                  </div>
                )}

                <span className="text-xs text-gray-400 mt-1 px-2">
                  {message.timestamp.toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </span>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-start space-x-3 animate-pulse">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="chat-bubble chat-bubble-assistant">
                <div className="flex space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="bg-white border-t border-gray-200 shadow-lg">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-end space-x-3">
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me about products, add items to cart, or complete your order..."
                className="input-field resize-none pr-12"
                rows={1}
                style={{
                  minHeight: '48px',
                  maxHeight: '120px',
                  height: 'auto'
                }}
                disabled={loading}
              />
              {input && (
                <button
                  onClick={() => setInput('')}
                  className="absolute right-3 top-3 text-gray-400 hover:text-gray-600 transition-colors"
                >
                  ×
                </button>
              )}
            </div>
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="btn-primary flex items-center space-x-2 h-12"
            >
              <Send className="w-4 h-4" />
              <span>Send</span>
            </button>
          </div>

          {/* Quick Actions */}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => setInput('Show me some cookies')}
              className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-gray-700 transition-colors"
              disabled={loading}
            >
              🍪 Show me cookies
            </button>
            <button
              onClick={() => setInput('What snacks do you have?')}
              className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-gray-700 transition-colors"
              disabled={loading}
            >
              🥨 Browse snacks
            </button>
            <button
              onClick={() => setInput('Show my cart')}
              className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-gray-700 transition-colors"
              disabled={loading}
            >
              🛒 View cart
            </button>
            <button
              onClick={() => setInput('I want to checkout')}
              className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-full text-gray-700 transition-colors"
              disabled={loading}
            >
              💳 Checkout
            </button>
          </div>
        </div>
      </div>

      {/* Checkout Popup */}
      {isRegistered && (
        <CheckoutPopup
          isOpen={showCheckout}
          onClose={() => setShowCheckout(false)}
          sessionId={sessionId}
          userEmail={userEmail}
          onPaymentSuccess={handlePaymentSuccess}
        />
      )}
    </div>
  )
}

export default App
