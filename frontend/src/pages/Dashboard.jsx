import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

export default function Dashboard() {
  const { data, loading, error } = useApi('/api/dashboard')

  if (loading) return <LoadingSpinner />
  if (error) return <div className="text-red-600 p-4">Error: {error}</div>

  const {
    today_updates,
    active_projects,
    active_members,
    active_reminders,
    recent_updates = [],
    blockers = [],
    action_items = [],
    last_report,
    date,
  } = data

  return (
    <div className="fade-in">
      <h1 className="text-2xl font-bold text-gray-800 mb-6">Dashboard</h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Today's Updates" value={today_updates} color="text-indigo-600" />
        <StatCard label="Active Projects" value={active_projects} color="text-green-600" />
        <StatCard label="Team Members" value={active_members} color="text-blue-600" />
        <StatCard label="Active Reminders" value={active_reminders} color="text-orange-600" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Blockers */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-lg font-semibold text-red-600 mb-3">Active Blockers</h2>
          {blockers.length > 0 ? (
            <ul className="space-y-2">
              {blockers.map((b, i) => (
                <li key={i} className="border-l-4 border-red-400 pl-3 py-1">
                  <div className="font-medium">{b.description}</div>
                  <div className="text-sm text-gray-500">
                    {b.project_name} - Blocking: {b.blocking_who}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-400 text-sm">No blockers today</p>
          )}
        </div>

        {/* Action Items */}
        <div className="bg-white rounded-lg shadow p-5">
          <h2 className="text-lg font-semibold text-amber-600 mb-3">Pending Action Items</h2>
          {action_items.length > 0 ? (
            <ul className="space-y-2">
              {action_items.map((a, i) => (
                <li key={i} className="flex items-start space-x-2">
                  <StatusBadge status={a.priority} className="mt-1" />
                  <div>
                    <div className="font-medium">{a.description}</div>
                    <div className="text-sm text-gray-500">Assigned: {a.assigned_to}</div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-400 text-sm">No pending action items</p>
          )}
        </div>

        {/* Recent Updates */}
        <div className="bg-white rounded-lg shadow p-5 lg:col-span-2">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-lg font-semibold text-gray-800">Today's Updates</h2>
            <Link to="/chat" className="text-indigo-600 text-sm hover:underline">
              Add Update
            </Link>
          </div>
          {recent_updates.length > 0 ? (
            <div className="space-y-3">
              {recent_updates.map((u) => (
                <div key={u._id} className="border rounded-lg p-3">
                  <div className="flex justify-between items-start">
                    <p className="text-gray-700">
                      {u.raw_text?.slice(0, 200)}
                      {u.raw_text?.length > 200 && '...'}
                    </p>
                    <span className="text-xs text-gray-400 whitespace-nowrap ml-3">
                      {u.source}
                      {u.has_screenshot && ' + img'}
                    </span>
                  </div>
                  {u.parsed?.team_updates && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {u.parsed.team_updates.map((tu, j) => (
                        <span key={j}>
                          <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded">
                            {tu.team_member_name}
                          </span>
                          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded ml-1">
                            {tu.project_name}
                          </span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-sm">
              No updates yet today.{' '}
              <Link to="/chat" className="text-indigo-600 hover:underline">
                Start adding updates
              </Link>
            </p>
          )}
        </div>

        {/* Last Report */}
        {last_report && (
          <div className="bg-white rounded-lg shadow p-5 lg:col-span-2">
            <h2 className="text-lg font-semibold text-gray-800 mb-3">Last Report</h2>
            <div className="flex items-center space-x-4 flex-wrap gap-2">
              <span
                className={`px-3 py-1 rounded-full text-sm font-medium ${
                  last_report.type === 'daily'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-purple-100 text-purple-700'
                }`}
              >
                {last_report.type?.charAt(0).toUpperCase() + last_report.type?.slice(1)}
              </span>
              <span className="text-gray-600">{last_report.date}</span>
              <span className="text-sm">
                Email:{' '}
                {last_report.delivery_status?.email?.sent ? (
                  <span className="text-green-600">Sent</span>
                ) : (
                  <span className="text-gray-400">Not sent</span>
                )}
              </span>
              <span className="text-sm">
                Telegram:{' '}
                {last_report.delivery_status?.telegram?.sent ? (
                  <span className="text-green-600">Sent</span>
                ) : (
                  <span className="text-gray-400">Not sent</span>
                )}
              </span>
              <Link to="/reports" className="text-indigo-600 text-sm hover:underline">
                View All
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div className="bg-white rounded-lg shadow p-5">
      <div className="text-sm text-gray-500">{label}</div>
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
    </div>
  )
}
