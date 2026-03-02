const colorMap = {
  active: 'bg-green-100 text-green-700',
  passive: 'bg-yellow-100 text-yellow-700',
  completed: 'bg-blue-100 text-blue-700',
  archived: 'bg-gray-100 text-gray-500',
  on_track: 'bg-green-100 text-green-700',
  at_risk: 'bg-orange-100 text-orange-700',
  off_track: 'bg-red-100 text-red-700',
  blocked: 'bg-red-100 text-red-700',
  in_progress: 'bg-blue-100 text-blue-700',
  high: 'bg-red-100 text-red-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-green-100 text-green-700',
}

export default function StatusBadge({ status, className = '' }) {
  const colors = colorMap[status] || 'bg-gray-100 text-gray-700'
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors} ${className}`}>
      {status ? status.replace(/_/g, ' ') : '--'}
    </span>
  )
}
