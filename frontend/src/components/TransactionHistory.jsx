import React from 'react'

function formatInr(paise) {
  return `Rs.${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
}

export default function TransactionHistory({ entries }) {
  if (!entries || entries.length === 0) return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-base font-semibold text-gray-900 mb-2">Ledger</h3>
      <p className="text-sm text-gray-400">No transactions yet.</p>
    </div>
  )

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-base font-semibold text-gray-900 mb-4">Recent Ledger Entries</h3>
      <div className="space-y-2 max-h-72 overflow-y-auto">
        {entries.map(entry => (
          <div key={entry.id} className="flex items-start justify-between py-2 border-b border-gray-50 last:border-0">
            <div className="flex items-center gap-2 min-w-0">
              <span className={`flex-shrink-0 w-1.5 h-1.5 rounded-full mt-1.5 ${
                entry.entry_type === 'credit' ? 'bg-green-500' : 'bg-red-400'
              }`} />
              <p className="text-xs text-gray-600 truncate">{entry.description}</p>
            </div>
            <span className={`flex-shrink-0 ml-3 text-sm font-medium ${
              entry.entry_type === 'credit' ? 'text-green-600' : 'text-red-500'
            }`}>
              {entry.entry_type === 'credit' ? '+' : '-'}{formatInr(entry.amount_paise)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
