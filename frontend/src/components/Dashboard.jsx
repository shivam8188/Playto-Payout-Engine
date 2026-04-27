import React, { useState, useEffect, useCallback } from 'react'
import { getMerchant } from '../api/client'
import BalanceCard from './BalanceCard'
import PayoutForm from './PayoutForm'
import PayoutTable from './PayoutTable'
import TransactionHistory from './TransactionHistory'

export default function Dashboard({ merchantId }) {
  const [merchant, setMerchant] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(() => {
    getMerchant(merchantId)
      .then(res => setMerchant(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [merchantId])

  useEffect(() => {
    setLoading(true)
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [refresh])

  if (loading) return <div className="text-gray-400 py-8 text-center">Loading merchant data...</div>
  if (!merchant) return <div className="text-red-400 py-8 text-center">Failed to load merchant</div>

  return (
    <div className="space-y-6">
      <BalanceCard merchant={merchant} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PayoutForm merchant={merchant} onSuccess={refresh} />
        <TransactionHistory entries={merchant.recent_ledger} />
      </div>
      <PayoutTable payouts={merchant.recent_payouts} onRefresh={refresh} />
    </div>
  )
}
