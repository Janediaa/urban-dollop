
import { useState } from 'react'
import {
  Activity,
  CalendarDays,
  ChevronRight,
  HeartPulse,
  LayoutDashboard,
  LogIn,
  Menu,
  Search,
  ShieldCheck,
  Stethoscope,
  UserRound,
  X,
} from 'lucide-react'
import './Sidebar.css'

const navigationGroups = [
  {
    label: 'WORKSPACE',
    items: [
      { id: 'overview', label: 'Overview', icon: LayoutDashboard },
      { id: 'medical', label: 'Medical AI', icon: HeartPulse },
      { id: 'doctors', label: 'Find doctors', icon: Stethoscope },
      { id: 'appointments', label: 'Appointments', icon: CalendarDays },
    ],
  },
]

export default function Sidebar({ activePage, setActivePage, authUser }) {
  const [isOpen, setIsOpen] = useState(false)

  function navigateTo(page) {
    setActivePage(page)
    setIsOpen(false)
  }

  return (
    <>
      <button
        type="button"
        className="mobile-menu-toggle"
        onClick={() => setIsOpen((previous) => !previous)}
        aria-label={isOpen ? 'Close navigation menu' : 'Open navigation menu'}
        aria-expanded={isOpen}
      >
        {isOpen ? <X size={21} /> : <Menu size={21} />}
      </button>

      {isOpen && (
        <button
          type="button"
          className="mobile-sidebar-backdrop"
          aria-label="Close navigation menu"
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside className={`app-sidebar ${isOpen ? 'is-open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-symbol">
            <Activity size={23} strokeWidth={2.5} />
          </div>

          <div className="brand-copy">
            <strong>Healthcare</strong>
            <span>Navigator</span>
          </div>
        </div>

        <div className="sidebar-patient-card">
          <div className="patient-card-icon">
            <HeartPulse size={19} />
          </div>

          <div className="patient-card-copy">
            <span>YOUR HEALTH</span>
            <strong>Made simpler.</strong>
          </div>

          <ShieldCheck size={17} className="patient-card-shield" />
        </div>

        <div className="sidebar-navigation">
          {navigationGroups.map((group) => (
            <div className="navigation-group" key={group.label}>
              <span className="navigation-label">{group.label}</span>

              <nav aria-label="Main navigation">
                {group.items.map((item) => {
                  const Icon = item.icon
                  const isActive = activePage === item.id

                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
                      onClick={() => navigateTo(item.id)}
                      aria-current={isActive ? 'page' : undefined}
                    >
                      <Icon size={19} strokeWidth={1.9} />
                      <span>{item.label}</span>

                      {isActive && (
                        <ChevronRight size={16} className="nav-chevron" />
                      )}
                    </button>
                  )
                })}
              </nav>
            </div>
          ))}
        </div>

        <div className="app-sidebar__bottom">
          <div className="sidebar-help-card">
            <div className="help-icon">
              <Search size={19} />
            </div>

            <strong>Need healthcare guidance?</strong>

            <p>
              Explore medical information and find the right healthcare
              professional.
            </p>

            <button type="button" onClick={() => navigateTo('medical')}>
              Explore Medical AI
              <ChevronRight size={15} />
            </button>
          </div>

          <div className="sidebar-account">
            <div className="account-avatar">
              {authUser?.full_name?.charAt(0)?.toUpperCase() || (
                <UserRound size={18} />
              )}
            </div>

            <div className="account-copy">
              <strong>{authUser?.full_name || 'Guest user'}</strong>
              <span>{authUser ? 'Patient account' : 'Not signed in'}</span>
            </div>

            {!authUser && (
              <button
                type="button"
                className="account-login"
                onClick={() => navigateTo('auth')}
                aria-label="Sign in"
              >
                <LogIn size={17} />
              </button>
            )}
          </div>
        </div>
      </aside>
    </>
  )
}
