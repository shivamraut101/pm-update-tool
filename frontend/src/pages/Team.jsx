import { useApi } from '../hooks/useApi'
import LoadingSpinner from '../components/LoadingSpinner'

export default function Team() {
  const { data, loading, error } = useApi('/api/team')

  if (loading) return <LoadingSpinner />
  if (error) return <div className="text-red-600 p-4">Error: {error}</div>

  const members = data || []

  return (
    <div className="fade-in">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Team Members</h1>
        <span className="text-sm text-gray-400">Synced from reference database</span>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Name</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Nickname</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Role</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Email</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Aliases</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {members.map((m) => (
              <tr key={m._id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{m.name}</td>
                <td className="px-4 py-3 text-gray-600">{m.nickname}</td>
                <td className="px-4 py-3 text-gray-600">{m.role}</td>
                <td className="px-4 py-3 text-gray-600 text-sm">{m.email}</td>
                <td className="px-4 py-3 text-gray-600 text-sm">
                  {m.aliases?.join(', ') || ''}
                </td>
                <td className="px-4 py-3">
                  {m.is_active ? (
                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
                      Active
                    </span>
                  ) : (
                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
                      Inactive
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {members.length === 0 && (
          <p className="text-center text-gray-400 py-8">
            No team members found. They will sync from the reference database on startup.
          </p>
        )}
      </div>
    </div>
  )
}
