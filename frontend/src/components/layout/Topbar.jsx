
import { LogIn, LogOut, UserRound } from 'lucide-react'
import './Topbar.css'

const pageTitles = {
  overview: 'Overview',
  medical: 'Medical AI',
  doctors: 'Find doctors',
  appointments: 'Appointments',
  auth: 'Your account',
}

export default function Topbar({
  activePage,
  authUser,
  onSignIn,
  onLogout,
}) {
  const pageTitle = pageTitles[activePage] || 'Healthcare Navigator'

  return (
    <header className="app-topbar">
      <div className="topbar-heading">
        <div className="topbar-breadcrumb">
          <span>Healthcare Navigator</span>
          <span className="breadcrumb-separator">/</span>
          <strong>{pageTitle}</strong>
        </div>

        <h1>{pageTitle}</h1>
      </div>

      <div className="topbar-actions">
        <div className="environment-indicator">
          <span className="environment-dot" />
          DEVELOPMENT
        </div>

        {authUser ? (
          <div className="topbar-user">
            <div className="topbar-user-avatar">
              {authUser.full_name?.charAt(0)?.toUpperCase() || (
                <UserRound size={17} />
              )}
            </div>

            <div className="topbar-user-details">
              <strong>{authUser.full_name}</strong>
              <span>Patient account</span>
            </div>

            <button
              type="button"
              className="topbar-action-button"
              onClick={onLogout}
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={17} />
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="topbar-signin-button"
            onClick={onSignIn}
          >
            <LogIn size={16} />
            Sign in
          </button>
        )}
      </div>
    </header>
  )
}
