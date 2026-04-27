import React, { useState } from 'react'
import { createPayout } from '../api/client'

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
  })
}

export default function PayoutForm({ merchant, onSuccess }) {
  const [amountInr, setAmountInr] = useState('')
  const [bankAccountId, setBankAccountId] = useState(merchant.bank_account_number)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setResult(null)

    const amountPaise = Math.round(parseFloat(amountInr) * 100)
    if (!amountPaise || amountPaise <= 0) {
      setResult({ type: 'error', message: 'Please enter a valid amount' })
      setLoading(false)
      return
    }

    const idempotencyKey = generateUUID()

    try {
      const res = await createPayout(
        merchant.id,
        { amount_paise: amountPaise, bank_account_id: bankAccountId },
        idempotencyKey
      )
      setResult({
        type: 'success',
        message: `Payout created! ID: ${res.data.id.slice(0, 8)}... Status: ${res.data.status}`
      })
      setAmountInr('')
      onSuccess()
    } catch (err) {
      const msg = err.response?.data?.error || 'Payout failed'
      const available = err.response?.data?.available_paise
      setResult({
        type: 'error',
        message: available !== undefined
          ? `${msg}. Available: Rs.${(available / 100).toFixed(2)}`
          : msg
      })
    } finally {
      setLoading(false)
    }
  }

  const availableInr = (merchant.available_balance_paise / 100).toFixed(2)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-base font-semibold text-gray-900 mb-4">Request Payout</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Amount (INR)</label>
          <input
            type="number"
            value={amountInr}
            onChange={e => setAmountInr(e.target.value)}
            placeholder={`Max Rs.${availableInr}`}
            step="0.01"
            min="0.01"
            required
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 mt-1">Available: Rs.{availableInr}</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Bank Account ID</label>
          <input
            type="text"
            value={bankAccountId}
            onChange={e => setBankAccountId(e.target.value)}
            required
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Processing...' : 'Request Payout'}
        </button>
      </form>
      {result && (
        <div className={`mt-4 p-3 rounded-lg text-sm ${
          result.type === 'success'
            ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {result.message}
        </div>
      )}
    </div>
  )
}
