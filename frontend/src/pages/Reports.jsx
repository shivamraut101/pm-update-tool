import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { api } from '../api/client'
import LoadingSpinner from '../components/LoadingSpinner'

export default function Reports() {
  const { data, loading, error, refetch } = useApi('/api/reports')
  const [status, setStatus] = useState({ text: '', type: '' })
  const [expanded, setExpanded] = useState({})

  if (loading) return <LoadingSpinner />
  if (error) return <div className="text-red-600 p-4">Error: {error}</div>

  const reports = data || []

  async function generateReport(type) {
    setStatus({ text: `Generating ${type} report...`, type: 'info' })
    try {
      const result = await api(`/api/reports/generate/${type}`, { method: 'POST' })
      if (result._id || result.content_html) {
        setStatus({
          text: `${type.charAt(0).toUpperCase() + type.slice(1)} report generated!`,
          type: 'success',
        })
        refetch()
      } else if (result.message) {
        setStatus({ text: result.message, type: 'warning' })
      }
    } catch (e) {
      setStatus({ text: `Error: ${e.message}`, type: 'error' })
    }
  }

  async function resendReport(id) {
    if (!confirm('Re-send this report via email and Telegram?')) return
    try {
      const result = await api(`/api/reports/${id}/send`, { method: 'POST' })
      const parts = []
      if (result.email) parts.push(`Email: ${result.email}`)
      if (result.telegram) parts.push(`Telegram: ${result.telegram}`)
      alert(parts.join('\n') || 'Report sent!')
      refetch()
    } catch (e) {
      alert(`Error: ${e.message}`)
    }
  }

  function toggleReport(id) {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const statusColors = {
    info: 'bg-blue-50 border-blue-200 text-blue-700',
    success: 'bg-green-50 border-green-200 text-green-700',
    warning: 'bg-yellow-50 border-yellow-200 text-yellow-700',
    error: 'bg-red-50 border-red-200 text-red-700',
  }

  return (
    <div className="fade-in max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Reports</h1>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => generateReport('daily')}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 text-sm font-medium transition"
          >
            Generate Daily Brief
          </button>
          <button
            onClick={() => generateReport('weekly')}
            className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 text-sm font-medium transition"
          >
            Generate Weekly Report
          </button>
        </div>
      </div>

      {status.text && (
        <div className={`rounded-lg p-3 mb-4 border ${statusColors[status.type]}`}>
          {status.text}
        </div>
      )}

      <div className="space-y-4">
        {reports.map((r) => {
          const delivery = r.delivery_status || {}
          const emailStatus = delivery.email || {}
          const telegramStatus = delivery.telegram || {}
          const stats = r.stats || {}

          return (
            <div
              key={r._id}
              className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow duration-200 p-5 border border-gray-100"
            >
              <div className="flex flex-col sm:flex-row justify-between items-start gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`px-3 py-1 rounded-full text-sm font-medium ${
                      r.type === 'daily'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-purple-100 text-purple-700'
                    }`}
                  >
                    {r.type?.charAt(0).toUpperCase() + r.type?.slice(1)}
                  </span>
                  <span className="font-medium text-gray-800">{r.date || 'N/A'}</span>
                  {r.type === 'weekly' && r.week_start && (
                    <span className="text-sm text-gray-500">
                      ({r.week_start} to {r.week_end})
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <DeliveryBadge label="Email" sent={emailStatus.sent} />
                  <DeliveryBadge label="TG" sent={telegramStatus.sent} />
                  <button
                    onClick={() => resendReport(r._id)}
                    className="text-indigo-600 hover:text-indigo-800 text-sm font-medium hover:underline transition"
                  >
                    Re-send
                  </button>
                  <button
                    onClick={() => toggleReport(r._id)}
                    className="text-gray-600 hover:text-gray-800 text-sm font-medium hover:underline transition"
                  >
                    {expanded[r._id] ? 'Hide' : 'View'}
                  </button>
                </div>
              </div>

              {/* Stats */}
              {Object.keys(stats).length > 0 && (
                <div className="flex flex-wrap gap-3 mt-3 text-xs text-gray-500">
                  {stats.update_count > 0 && <span>{stats.update_count} update(s)</span>}
                  {stats.project_count > 0 && <span>{stats.project_count} project(s)</span>}
                  {stats.blocker_count > 0 && (
                    <span className="text-red-500">{stats.blocker_count} blocker(s)</span>
                  )}
                  {stats.action_item_count > 0 && (
                    <span className="text-amber-600">{stats.action_item_count} action item(s)</span>
                  )}
                  {stats.days_with_reports > 0 && (
                    <span>{stats.days_with_reports}/5 days reported</span>
                  )}
                </div>
              )}

              {/* Executive summary */}
              {r.executive_summary && (
                <p className="mt-3 text-sm text-gray-600 italic border-l-2 border-indigo-300 pl-3">
                  {r.executive_summary.slice(0, 200)}
                  {r.executive_summary.length > 200 && '...'}
                </p>
              )}

              {/* Expandable content */}
              {expanded[r._id] && (
                <div className="mt-4 border-t border-gray-200 pt-4">
                  <div className="bg-gray-50 rounded-lg p-4 overflow-auto max-h-[600px]">
                    {r.content_html ? (
                      <div
                        className="prose prose-sm max-w-none [&>*]:max-w-full [&_body]:!max-w-full [&_body]:!mx-0 [&_body]:!p-0"
                        dangerouslySetInnerHTML={{ __html: r.content_html }}
                      />
                    ) : r.content_markdown ? (
                      <pre className="whitespace-pre-wrap break-words text-sm text-gray-700 font-mono bg-white rounded p-3 border border-gray-200 overflow-x-auto">
                        {r.content_markdown}
                      </pre>
                    ) : (
                      <p className="text-gray-400 italic">No content available.</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {reports.length === 0 && (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg
            className="w-20 h-20 mx-auto text-gray-300 mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="1.5"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <h3 className="text-xl font-semibold text-gray-700 mb-2">No reports generated yet</h3>
          <p className="text-gray-500 mb-4">Submit some updates first, then generate a daily brief.</p>
          <button
            onClick={() => generateReport('daily')}
            className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 text-sm font-medium transition"
          >
            Generate Your First Report
          </button>
        </div>
      )}
    </div>
  )
}

function DeliveryBadge({ label, sent }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full border ${
        sent
          ? 'bg-green-50 text-green-700 border-green-200'
          : 'bg-gray-50 text-gray-400 border-gray-200'
      }`}
    >
      {label}: {sent ? 'Sent' : 'Pending'}
    </span>
  )
}
