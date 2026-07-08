import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Sidebar({ pages, activePage, onNavigate }) {
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    const fetchPending = async () => {
      try {
        const data = await api.getApprovals('pending')
        setPendingCount(Array.isArray(data) ? data.length : 0)
      } catch { /* ignore */ }
    }
    fetchPending()
    const interval = setInterval(fetchPending, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <div className="brand-icon">H</div>
        <div className="brand-text">
          <h2>HobbyFi</h2>
          <span>AI Copilot</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {Object.entries(pages).map(([key, page]) => (
          <div
            key={key}
            className={`nav-item${activePage === key ? ' active' : ''}`}
            onClick={() => onNavigate(key)}
          >
            <span className="nav-icon">{page.icon}</span>
            <span>{page.label}</span>
            {key === 'approvals' && pendingCount > 0 && (
              <span className="nav-badge">{pendingCount}</span>
            )}
          </div>
        ))}
      </nav>

      {/* Footer — Vendor Profile */}
      <div className="sidebar-footer">
        <div className="vendor-avatar">MK</div>
        <div className="vendor-info">
          <div className="vendor-name">Mahesh Kumar</div>
          <div className="vendor-role">Vendor Admin</div>
        </div>
      </div>
    </aside>
  )
}
