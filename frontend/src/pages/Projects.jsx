import { useApi } from '../hooks/useApi'
import LoadingSpinner from '../components/LoadingSpinner'
import StatusBadge from '../components/StatusBadge'

export default function Projects() {
  const { data, loading, error } = useApi('/api/projects')

  if (loading) return <LoadingSpinner />
  if (error) return <div className="text-red-600 p-4">Error: {error}</div>

  const projects = data || []

  return (
    <div className="fade-in">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Projects</h1>
        <span className="text-sm text-gray-400">Synced from reference database</span>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Name</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Code</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Status</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Health</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Tech Stack</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Team</th>
              <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Repo</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {projects.map((p) => (
              <tr key={p._id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{p.name}</td>
                <td className="px-4 py-3 text-gray-600">{p.code}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={p.status} />
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={p.health} />
                </td>
                <td className="px-4 py-3 text-gray-600 text-sm">
                  {p.tech_stack?.length > 0 ? p.tech_stack.join(', ') : '--'}
                </td>
                <td className="px-4 py-3 text-gray-600">
                  {p.team_member_ids?.length || 0} members
                </td>
                <td className="px-4 py-3">
                  {p.repository_url ? (
                    <a
                      href={p.repository_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:text-indigo-800 text-sm"
                    >
                      GitHub
                    </a>
                  ) : (
                    <span className="text-gray-400 text-sm">--</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {projects.length === 0 && (
          <p className="text-center text-gray-400 py-8">
            No projects found. They will sync from the reference database on startup.
          </p>
        )}
      </div>
    </div>
  )
}
