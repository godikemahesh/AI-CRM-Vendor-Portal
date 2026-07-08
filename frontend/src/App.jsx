import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import ChatPanel from './components/ChatPanel'
import ApprovalQueue from './components/ApprovalQueue'
import AuditLog from './components/AuditLog'

const PAGES = {
  dashboard:  { label: 'Dashboard',  icon: '📊', component: Dashboard },
  copilot:    { label: 'AI Copilot', icon: '🤖', component: ChatPanel },
  approvals:  { label: 'Approvals',  icon: '✅', component: ApprovalQueue },
  audit:      { label: 'Audit Log',  icon: '📋', component: AuditLog },
}

export default function App() {
  const [activePage, setActivePage] = useState('dashboard')

  return (
    <div className="app-layout">
      <Sidebar
        pages={PAGES}
        activePage={activePage}
        onNavigate={setActivePage}
      />
      <main className="main-content">
        <div style={{ display: activePage === 'dashboard' ? 'block' : 'none' }}>
          <Dashboard activePage={activePage} />
        </div>
        <div style={{ display: activePage === 'copilot' ? 'block' : 'none' }}>
          <ChatPanel activePage={activePage} />
        </div>
        <div style={{ display: activePage === 'approvals' ? 'block' : 'none' }}>
          <ApprovalQueue activePage={activePage} />
        </div>
        <div style={{ display: activePage === 'audit' ? 'block' : 'none' }}>
          <AuditLog activePage={activePage} />
        </div>
      </main>
    </div>
  )
}

