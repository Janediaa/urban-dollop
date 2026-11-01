
import Sidebar from './Sidebar'
import Topbar from './Topbar'
import './AppLayout.css'

export default function AppLayout({
  activePage,
  setActivePage,
  authUser,
  onSignIn,
  onLogout,
  children,
}) {
  return (
    <div className="app-layout">
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
        authUser={authUser}
      />

      <div className="app-main">
        <Topbar
          activePage={activePage}
          authUser={authUser}
          onSignIn={onSignIn}
          onLogout={onLogout}
        />

        <main className="app-content">
          {children}
        </main>
      </div>
    </div>
  )
}
