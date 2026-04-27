import React, { useState, useEffect } from 'react'
import { getMerchants } from './api/client'
import Dashboard from './components/Dashboard'

export default function App() {
  const [merchants, setMerchants] = useState([])
  const [selectedMerchantId, setSelectedMerchantId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getMerchants()
      .then(res => {
        setMerchants(res.data)
        if (res.data.length > 0) setSelectedMerchantId(res.data[0].id)
      })
      .catch(() => setError('Failed to load merchants. Is the backend running?'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-gray-500 text-lg">Loading...</div>
    </div>
  )

  if (error) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-red-500 text-center">
        <p className="text-lg font-medium">{error}</p>
        <p className="text-sm mt-2">Make sure Django is running on port 8000</p>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">Playto Pay — Payout Engine</h1>
          <select
            value={selectedMerchantId || ''}
            onChange={e => setSelectedMerchantId(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {merchants.map(m => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">
        {selectedMerchantId && <Dashboard merchantId={selectedMerchantId} />}
      </main>
    </div>
  )
}
