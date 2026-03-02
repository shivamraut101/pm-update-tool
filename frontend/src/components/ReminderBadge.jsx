import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import { usePolling } from '../hooks/usePolling'

export default function ReminderBadge() {
  const [count, setCount] = useState(0)

  const fetchCount = useCallback(() => {
    api('/api/reminders/count')
      .then((data) => setCount(data.count || 0))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchCount()
  }, [fetchCount])

  usePolling(fetchCount, 60000)

  if (count === 0) return null

  return (
    <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
      {count}
    </span>
  )
}
