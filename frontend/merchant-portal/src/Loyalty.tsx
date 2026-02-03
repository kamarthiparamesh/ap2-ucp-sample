import { useState, useEffect } from 'react'
import axios from 'axios'
import { ArrowLeft, Users, Star, Trophy, TrendingUp, Award, Gift } from 'lucide-react'

interface LoyaltyUser {
  email: string
  points: number
  tier: string
  tier_benefits: {
    discount_percentage: number
    points_multiplier: number
    perks: string[]
  }
  transaction_count: number
  last_updated: string
}

interface LoyaltyStats {
  total_members: number
  total_points_distributed: number
  tier_breakdown: {
    bronze: number
    silver: number
    gold: number
    platinum: number
  }
  total_transactions: number
}

interface Props {
  onBackToProducts: () => void
}

function Loyalty({ onBackToProducts }: Props) {
  const [users, setUsers] = useState<LoyaltyUser[]>([])
  const [stats, setStats] = useState<LoyaltyStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedUser, setSelectedUser] = useState<string | null>(null)

  useEffect(() => {
    fetchLoyaltyData()
  }, [])

  const fetchLoyaltyData = async () => {
    try {
      const [usersResponse, statsResponse] = await Promise.all([
        axios.get('/api/loyalty/users'),
        axios.get('/api/loyalty/stats')
      ])

      setUsers(usersResponse.data.users || [])
      setStats(statsResponse.data)
    } catch (error) {
      console.error('Error fetching loyalty data:', error)
    } finally {
      setLoading(false)
    }
  }

  const getTierColor = (tier: string) => {
    switch (tier.toLowerCase()) {
      case 'platinum':
        return 'bg-gradient-to-r from-gray-400 to-gray-600 text-white'
      case 'gold':
        return 'bg-gradient-to-r from-yellow-400 to-yellow-600 text-white'
      case 'silver':
        return 'bg-gradient-to-r from-gray-300 to-gray-400 text-gray-800'
      default:
        return 'bg-gradient-to-r from-amber-600 to-amber-800 text-white'
    }
  }

  const getTierIcon = (tier: string) => {
    switch (tier.toLowerCase()) {
      case 'platinum':
        return <Trophy className="w-5 h-5" />
      case 'gold':
        return <Award className="w-5 h-5" />
      case 'silver':
        return <Star className="w-5 h-5" />
      default:
        return <Gift className="w-5 h-5" />
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center space-x-4">
            <button
              onClick={onBackToProducts}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Loyalty Management</h1>
              <p className="text-sm text-gray-500">Manage your customer loyalty program</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="mt-4 text-gray-600">Loading loyalty data...</p>
          </div>
        ) : (
          <>
            {/* Stats Cards */}
            {stats && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div className="card">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600 mb-1">Total Members</p>
                      <p className="text-3xl font-bold text-gray-800">{stats.total_members}</p>
                    </div>
                    <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                      <Users className="w-6 h-6 text-blue-600" />
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600 mb-1">Total Points</p>
                      <p className="text-3xl font-bold text-gray-800">
                        {stats.total_points_distributed.toLocaleString()}
                      </p>
                    </div>
                    <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                      <Star className="w-6 h-6 text-purple-600" />
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600 mb-1">Transactions</p>
                      <p className="text-3xl font-bold text-gray-800">{stats.total_transactions}</p>
                    </div>
                    <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                      <TrendingUp className="w-6 h-6 text-green-600" />
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600 mb-1">Gold+ Members</p>
                      <p className="text-3xl font-bold text-gray-800">
                        {(stats.tier_breakdown.gold || 0) + (stats.tier_breakdown.platinum || 0)}
                      </p>
                    </div>
                    <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
                      <Trophy className="w-6 h-6 text-yellow-600" />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Tier Breakdown */}
            {stats && (
              <div className="card mb-8">
                <h2 className="text-xl font-bold text-gray-800 mb-6">Membership Tiers</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(stats.tier_breakdown).map(([tier, count]) => (
                    <div
                      key={tier}
                      className={`p-4 rounded-lg ${getTierColor(tier)}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium uppercase">{tier}</span>
                        {getTierIcon(tier)}
                      </div>
                      <p className="text-2xl font-bold">{count}</p>
                      <p className="text-xs opacity-90">members</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Members Table */}
            <div className="card">
              <h2 className="text-xl font-bold text-gray-800 mb-6">Loyalty Members</h2>

              {users.length === 0 ? (
                <div className="text-center py-12">
                  <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-600">No loyalty members yet</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b-2 border-gray-200">
                        <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">
                          Member
                        </th>
                        <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">
                          Tier
                        </th>
                        <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">
                          Points
                        </th>
                        <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">
                          Multiplier
                        </th>
                        <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">
                          Discount
                        </th>
                        <th className="text-left py-3 px-4 font-semibold text-gray-700 text-sm">
                          Transactions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((user) => (
                        <tr
                          key={user.email}
                          className="table-row cursor-pointer"
                          onClick={() => setSelectedUser(user.email)}
                        >
                          <td className="py-3 px-4">
                            <div className="flex items-center space-x-3">
                              <div className="w-10 h-10 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center">
                                <span className="text-white font-semibold text-sm">
                                  {user.email.charAt(0).toUpperCase()}
                                </span>
                              </div>
                              <div>
                                <p className="font-medium text-gray-800">{user.email}</p>
                                <p className="text-xs text-gray-500">
                                  {user.tier_benefits.perks.length} perks
                                </p>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <span
                              className={`inline-flex items-center space-x-2 px-3 py-1.5 rounded-full text-xs font-medium ${getTierColor(
                                user.tier
                              )}`}
                            >
                              {getTierIcon(user.tier)}
                              <span className="uppercase">{user.tier}</span>
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className="font-semibold text-gray-800">
                              {user.points.toLocaleString()}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className="text-gray-600">
                              {user.tier_benefits.points_multiplier}x
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className="text-green-600 font-medium">
                              {user.tier_benefits.discount_percentage}%
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <span className="text-gray-600">{user.transaction_count}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export default Loyalty
