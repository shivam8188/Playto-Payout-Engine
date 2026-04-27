import React from 'react'

function formatInr(paise) {
  const inr = paise / 100
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(inr)
}

export default function BalanceCard({ merchant }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{merchant.name}</h2>
          <p className="text-sm text-gray-500">{merchant.email}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-400 uppercase tracking-wide">Bank IFSC</p>
          <p className="text-sm text-gray-600">{merchant.bank_ifsc}</p>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-green-50 rounded-lg p-4">
          <p className="text-xs text-green-600 font-medium uppercase tracking-wide mb-1">Available</p>
          <p className="text-2xl font-bold text-green-700">{formatInr(merchant.available_balance_paise)}</p>
          <p className="text-xs text-green-500 mt-1">Ready to withdraw</p>
        </div>
        <div className="bg-yellow-50 rounded-lg p-4">
          <p className="text-xs text-yellow-600 font-medium uppercase tracking-wide mb-1">Held</p>
          <p className="text-2xl font-bold text-yellow-700">{formatInr(merchant.held_balance_paise)}</p>
          <p className="text-xs text-yellow-500 mt-1">Pending payouts</p>
        </div>
        <div className="bg-blue-50 rounded-lg p-4">
          <p className="text-xs text-blue-600 font-medium uppercase tracking-wide mb-1">Total</p>
          <p className="text-2xl font-bold text-blue-700">{formatInr(merchant.total_balance_paise)}</p>
          <p className="text-xs text-blue-500 mt-1">Credits minus Debits</p>
        </div>
      </div>
    </div>
  )
}
