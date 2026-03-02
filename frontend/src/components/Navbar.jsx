import { NavLink } from 'react-router-dom'
import ReminderBadge from './ReminderBadge'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/chat', label: 'Chat' },
  { to: '/projects', label: 'Projects' },
  { to: '/team', label: 'Team' },
  { to: '/reports', label: 'Reports' },
  { to: '/reminders', label: 'Reminders', badge: true },
  { to: '/settings', label: 'Settings' },
]

export default function Navbar() {
  return (
    <nav className="bg-indigo-600 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-2">
            <span className="text-xl font-bold">PM Update Tool</span>
          </div>
          <div className="flex items-center space-x-1">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/'}
                className={({ isActive }) =>
                  `relative px-3 py-2 rounded-md text-sm font-medium transition-colors hover:bg-white/10 ${
                    isActive ? 'bg-white/20' : ''
                  }`
                }
              >
                {link.label}
                {link.badge && <ReminderBadge />}
              </NavLink>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
}
