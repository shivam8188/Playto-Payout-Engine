import React from 'react'

const STATUS_STYLES = {
  pending: 'bg-yellow-100 text-yellow-700',
  processing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

function formatInr(paise) {
  return `Rs.${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
}

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
  })
}

export default function PayoutTable({ payouts, onRefresh }) {
  if (!payouts || payouts.length === 0) return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-base font-semibold text-gray-900 mb-2">Payout History</h3>
      <p className="text-sm text-gray-400">No payouts yet. Request your first payout above.</p>
    </div>
  )

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-gray-900">Payout History</h3>
        <button
          onClick={onRefresh}
          className="text-xs text-blue-600 hover:text-blue-800 font-medium"
        >
          Refresh
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left text-xs text-gray-400 font-medium py-2 pr-4">ID</th>
              <th className="text-right text-xs text-gray-400 font-medium py-2 pr-4">Amount</th>
              <th className="text-left text-xs text-gray-400 font-medium py-2 pr-4">Status</th>
              <th className="text-right text-xs text-gray-400 font-medium py-2 pr-4">Attempts</th>
              <th className="text-left text-xs text-gray-400 font-medium py-2">Created</th>
            </tr>
          </thead>
          <tbody>
            {payouts.map(payout => (
              <tr key={payout.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-2.5 pr-4 font-mono text-xs text-gray-500">
                  {payout.id.slice(0, 8)}...
                </td>
                <td className="py-2.5 pr-4 text-right font-medium text-gray-900">
                  {formatInr(payout.amount_paise)}
                </td>
                <td className="py-2.5 pr-4">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[payout.status] || 'bg-gray-100 text-gray-600'}`}>
                    {payout.status}
                  </span>
                  {payout.failure_reason && (
                    <span className="ml-2 text-xs text-red-400">{payout.failure_reason}</span>
                  )}
                </td>
                <td className="py-2.5 pr-4 text-right text-gray-500">
                  {payout.attempt_count}/{payout.max_attempts}
                </td>
                <td className="py-2.5 text-xs text-gray-400">
                  {formatDate(payout.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
