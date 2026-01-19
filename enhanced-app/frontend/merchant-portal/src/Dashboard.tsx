import { useState, useEffect } from 'react'
import axios from 'axios'
import { Activity, Code, CreditCard, RefreshCw, Filter, ChevronDown, ChevronUp, ArrowLeft, Trash2 } from 'lucide-react'

interface UCPLog {
  id: string
  endpoint: string
  method: string
  query_params: Record<string, any>
  request_body: any
  response_status: number
  response_body: any
  client_ip: string
  user_agent: string
  duration_ms: number
  created_at: string
}

interface AP2Log {
  id: string
  endpoint: string
  method: string
  message_type: string
  mandate_id: string | null
  request_body: any
  request_signature: string | null
  response_status: number
  response_body: any
  response_signature: string | null
  payment_status: string | null
  client_ip: string
  user_agent: string
  duration_ms: number
  created_at: string
}

interface DashboardStats {
  total_ucp_requests: number
  total_ap2_requests: number
  successful_payments: number
  timestamp: string
}

interface DashboardProps {
  onBackToProducts?: () => void
}

function Dashboard({ onBackToProducts }: DashboardProps) {
  const [activeTab, setActiveTab] = useState<'ucp' | 'ap2'>('ucp')
  const [ucpLogs, setUcpLogs] = useState<UCPLog[]>([])
  const [ap2Logs, setAP2Logs] = useState<AP2Log[]>([])
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(false)

  useEffect(() => {
    fetchData()

    let interval: any
    if (autoRefresh) {
      interval = setInterval(fetchData, 5000) // Refresh every 5 seconds
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [autoRefresh, activeTab])

  const fetchData = async () => {
    try {
      const [ucpResponse, ap2Response, statsResponse] = await Promise.all([
        axios.get('/api/dashboard/ucp-logs?limit=50'),
        axios.get('/api/dashboard/ap2-logs?limit=50'),
        axios.get('/api/dashboard/stats')
      ])

      setUcpLogs(ucpResponse.data.logs)
      setAP2Logs(ap2Response.data.logs)
      setStats(statsResponse.data)
    } catch (error) {
      console.error('Error fetching dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleLogExpansion = (logId: string) => {
    setExpandedLogId(expandedLogId === logId ? null : logId)
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  const getStatusColor = (status: number) => {
    if (status >= 200 && status < 300) return 'text-green-600 bg-green-50'
    if (status >= 400 && status < 500) return 'text-yellow-600 bg-yellow-50'
    return 'text-red-600 bg-red-50'
  }

  const clearAllLogs = async () => {
    if (!confirm('Are you sure you want to clear all logs? This action cannot be undone.')) {
      return
    }

    try {
      await axios.delete('/api/dashboard/clear-logs')
      // Refresh data after clearing
      await fetchData()
    } catch (error) {
      console.error('Error clearing logs:', error)
      alert('Failed to clear logs. Please try again.')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-6">
          {onBackToProducts && (
            <button
              onClick={onBackToProducts}
              className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 mb-4 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Products</span>
            </button>
          )}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">API Dashboard</h1>
              <p className="text-gray-600 mt-1">Monitor UCP and AP2 protocol requests</p>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={clearAllLogs}
                className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                <span>Clear All Logs</span>
              </button>
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  autoRefresh
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <RefreshCw className={`w-4 h-4 S${autoRefresh ? 'animate-spin' : ''}`} />
                <span>{autoRefresh ? 'Auto-refreshing' : 'Auto-refresh OFF'}</span>
              </button>
            </div>
          </div>

          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
              <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-blue-600 font-medium">UCP Requests</p>
                    <p className="text-3xl font-bold text-blue-900 mt-1">{stats.total_ucp_requests}</p>
                  </div>
                  <Activity className="w-10 h-10 text-blue-600 opacity-50" />
                </div>
              </div>

              <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-purple-600 font-medium">AP2 Requests</p>
                    <p className="text-3xl font-bold text-purple-900 mt-1">{stats.total_ap2_requests}</p>
                  </div>
                  <Code className="w-10 h-10 text-purple-600 opacity-50" />
                </div>
              </div>

              <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-green-600 font-medium">Successful Payments</p>
                    <p className="text-3xl font-bold text-green-900 mt-1">{stats.successful_payments}</p>
                  </div>
                  <CreditCard className="w-10 h-10 text-green-600 opacity-50" />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 mt-6">
        <div className="flex space-x-2 border-b border-gray-200">
          <button
            onClick={() => setActiveTab('ucp')}
            className={`px-6 py-3 font-medium transition-colors border-b-2 ${
              activeTab === 'ucp'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            UCP Requests ({ucpLogs.length})
          </button>
          <button
            onClick={() => setActiveTab('ap2')}
            className={`px-6 py-3 font-medium transition-colors border-b-2 ${
              activeTab === 'ap2'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            AP2 Messages ({ap2Logs.length})
          </button>
        </div>

        {/* Logs Content */}
        <div className="mt-6 space-y-4 pb-8">
          {activeTab === 'ucp' && (
            <>
              {ucpLogs.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
                  <Activity className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-600">No UCP requests logged yet</p>
                </div>
              ) : (
                ucpLogs.map((log) => (
                  <div key={log.id} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                    <div
                      className="px-6 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
                      onClick={() => toggleLogExpansion(log.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4 flex-1">
                          <span className={`px-2 py-1 rounded text-xs font-medium S${getStatusColor(log.response_status)}`}>
                            {log.response_status}
                          </span>
                          <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium">
                            {log.method}
                          </span>
                          <span className="font-mono text-sm text-gray-900">{log.endpoint}</span>
                          {log.duration_ms && (
                            <span className="text-xs text-gray-500">{log.duration_ms.toFixed(2)}ms</span>
                          )}
                        </div>
                        <div className="flex items-center space-x-4">
                          <span className="text-sm text-gray-500">{formatTimestamp(log.created_at)}</span>
                          {expandedLogId === log.id ? (
                            <ChevronUp className="w-5 h-5 text-gray-400" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-400" />
                          )}
                        </div>
                      </div>
                    </div>

                    {expandedLogId === log.id && (
                      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <h4 className="text-sm font-semibold text-gray-700 mb-2">Request Details</h4>
                            <div className="space-y-2 text-sm">
                              <div><span className="font-medium">Client IP:</span> {log.client_ip || 'N/A'}</div>
                              <div><span className="font-medium">User Agent:</span> {log.user_agent || 'N/A'}</div>
                              {Object.keys(log.query_params || {}).length > 0 && (
                                <div>
                                  <span className="font-medium">Query Params:</span>
                                  <pre className="mt-1 p-2 bg-white rounded border border-gray-200 text-xs overflow-x-auto">
                                    {JSON.stringify(log.query_params, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {log.request_body && (
                                <div>
                                  <span className="font-medium">Request Body:</span>
                                  <pre className="mt-1 p-2 bg-white rounded border border-gray-200 text-xs overflow-x-auto">
                                    {JSON.stringify(log.request_body, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          </div>

                          <div>
                            <h4 className="text-sm font-semibold text-gray-700 mb-2">Response</h4>
                            {log.response_body ? (
                              <pre className="p-2 bg-white rounded border border-gray-200 text-xs overflow-x-auto max-h-96">
                                {JSON.stringify(log.response_body, null, 2)}
                              </pre>
                            ) : (
                              <p className="text-sm text-gray-500">No response body logged</p>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </>
          )}

          {activeTab === 'ap2' && (
            <>
              {ap2Logs.length === 0 ? (
                <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
                  <CreditCard className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-600">No AP2 payment messages logged yet</p>
                </div>
              ) : (
                ap2Logs.map((log) => (
                  <div key={log.id} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                    <div
                      className="px-6 py-4 cursor-pointer hover:bg-gray-50 transition-colors"
                      onClick={() => toggleLogExpansion(log.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4 flex-1">
                          <span className={`px-2 py-1 rounded text-xs font-medium S${getStatusColor(log.response_status)}`}>
                            {log.response_status}
                          </span>
                          <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-medium">
                            {log.message_type}
                          </span>
                          <span className="font-mono text-sm text-gray-900">{log.endpoint}</span>
                          {log.mandate_id && (
                            <span className="text-xs text-gray-500">Mandate: {log.mandate_id.substring(0, 12)}...</span>
                          )}
                          {log.payment_status && (
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              log.payment_status === 'success' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                            }`}>
                              {log.payment_status}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center space-x-4">
                          <span className="text-sm text-gray-500">{formatTimestamp(log.created_at)}</span>
                          {expandedLogId === log.id ? (
                            <ChevronUp className="w-5 h-5 text-gray-400" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-400" />
                          )}
                        </div>
                      </div>
                    </div>

                    {expandedLogId === log.id && (
                      <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
                        <div className="grid grid-cols-1 gap-4">
                          <div>
                            <h4 className="text-sm font-semibold text-gray-700 mb-2">Request Message (AP2 Protocol)</h4>
                            <div className="space-y-2 text-sm mb-4">
                              <div><span className="font-medium">Client IP:</span> {log.client_ip || 'N/A'}</div>
                              <div><span className="font-medium">User Agent:</span> {log.user_agent || 'N/A'}</div>
                              {log.request_signature && (
                                <div>
                                  <span className="font-medium">User Signature (WebAuthn):</span>
                                  <pre className="mt-1 p-2 bg-white rounded border border-gray-200 text-xs overflow-x-auto font-mono">
                                    {log.request_signature}
                                  </pre>
                                </div>
                              )}
                            </div>
                            <span className="font-medium text-sm">Full AP2 Request Body:</span>
                            <pre className="mt-1 p-2 bg-white rounded border border-gray-200 text-xs overflow-x-auto max-h-96">
                              {JSON.stringify(log.request_body, null, 2)}
                            </pre>
                          </div>

                          <div>
                            <h4 className="text-sm font-semibold text-gray-700 mb-2">Response Message (AP2 Protocol)</h4>
                            {log.response_signature && (
                              <div className="mb-2">
                                <span className="font-medium text-sm">Merchant Signature:</span>
                                <pre className="mt-1 p-2 bg-white rounded border border-gray-200 text-xs overflow-x-auto font-mono">
                                  {log.response_signature}
                                </pre>
                              </div>
                            )}
                            <span className="font-medium text-sm">Full AP2 Response Body:</span>
                            <pre className="mt-1 p-2 bg-white rounded border border-gray-200 text-xs overflow-x-auto max-h-96">
                              {JSON.stringify(log.response_body, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default Dashboard
