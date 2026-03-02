import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'

export default function Reminders() {
  const { data, loading, error, refetch } = useApi('/api/reminders?active_only=false')
  const [showDismissed, setShowDismissed] = useState(false)

  if (loading) return <LoadingSpinner />
  if (error) return <div className="text-red-600 p-4">Error: {error}</div>

  const all = data || []
  const active = all.filter((r) => !r.is_dismissed)
  const dismissed = all.filter((r) => r.is_dismissed)

  async function dismissReminder(id) {
    await api(`/api/reminders/${id}/dismiss`, { method: 'PUT' })
    refetch()
  }

  async function actOnReminder(id) {
    await api(`/api/reminders/${id}/act`, { method: 'POST' })
    refetch()
  }

  const priorityBorder = {
    high: 'border-red-500',
    medium: 'border-yellow-500',
    low: 'border-green-500',
  }

  const typeColors = {
    no_update_today: 'bg-orange-100 text-orange-700',
    blocker_unresolved: 'bg-red-100 text-red-700',
    action_item_due: 'bg-amber-100 text-amber-700',
  }

  return (
    <div className="fade-in">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Reminders</h1>

      {/* Active */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-700 mb-3">Active ({active.length})</h2>
        {active.length > 0 ? (
          <div className="space-y-3">
            {active.map((r) => (
              <div
                key={r._id}
                className={`bg-white rounded-lg shadow p-4 border-l-4 ${
                  priorityBorder[r.priority] || 'border-blue-500'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-1">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          typeColors[r.type] || 'bg-blue-100 text-blue-700'
                        }`}
                      >
                        {r.type?.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                      </span>
                      <span className="text-xs text-gray-400">{r.trigger_time}</span>
                    </div>
                    <p className="text-gray-800">{r.message}</p>
                  </div>
                  <div className="flex space-x-2 ml-4">
                    <button
                      onClick={() => actOnReminder(r._id)}
                      className="text-indigo-600 hover:text-indigo-800 text-sm"
                    >
                      Act
                    </button>
                    <button
                      onClick={() => dismissReminder(r._id)}
                      className="text-gray-400 hover:text-gray-600 text-sm"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400 bg-white rounded-lg shadow p-6 text-center">
            No active reminders. All caught up!
          </p>
        )}
      </div>

      {/* Dismissed */}
      {dismissed.length > 0 && (
        <div>
          <button
            onClick={() => setShowDismissed(!showDismissed)}
            className="text-sm text-gray-500 hover:text-gray-700 mb-3"
          >
            {showDismissed ? 'Hide' : 'Show'} Dismissed ({dismissed.length})
          </button>
          {showDismissed && (
            <div className="space-y-2">
              {dismissed.map((r) => (
                <div key={r._id} className="bg-gray-50 rounded-lg p-3 opacity-60">
                  <span className="text-xs text-gray-400">
                    {r.type?.replace(/_/g, ' ')}
                  </span>
                  <p className="text-sm text-gray-500">{r.message}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
