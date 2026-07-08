import { useState, useEffect } from 'react'
import { api } from '../api'

export default function ApprovalQueue({ activePage }) {
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all') // 'all' | 'pending'

  const load = async () => {
    try {
      const status = filter === 'pending' ? 'pending' : undefined
      const data = await api.getApprovals(status)
      setActions(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error('Failed to load approvals:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setLoading(true)
    load()
  }, [filter])

  useEffect(() => {
    if (activePage === 'approvals') {
      load()
    }
  }, [activePage])

  // Poll for updates
  useEffect(() => {
    const interval = setInterval(load, 8000)
    return () => clearInterval(interval)
  }, [filter])

  const handleApprove = async (id) => {
    try {
      await api.approve(id)
      load()
    } catch (err) {
      alert('Approve failed: ' + err.message)
    }
  }

  const handleReject = async (id) => {
    try {
      await api.reject(id)
      load()
    } catch (err) {
      alert('Reject failed: ' + err.message)
    }
  }

  const formatTime = (ts) => {
    if (!ts) return ''
    return new Date(ts).toLocaleString('en-IN', {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    })
  }

  const parseJson = (val) => {
    if (!val) return null
    if (typeof val === 'object') return val
    try { return JSON.parse(val) } catch { return null }
  }

  return (
    <>
      <div className="page-header">
        <h1>Approval Queue</h1>
        <p>Review and approve AI-proposed write operations</p>
      </div>

      <div className="audit-filters" style={{ marginBottom: 20 }}>
        <button
          className={`filter-btn${filter === 'all' ? ' active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All Actions
        </button>
        <button
          className={`filter-btn${filter === 'pending' ? ' active' : ''}`}
          onClick={() => setFilter('pending')}
        >
          ⏳ Pending Only
        </button>
      </div>

      {loading ? (
        <div className="loading-spinner" />
      ) : actions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">✅</div>
          <h3>No {filter === 'pending' ? 'pending ' : ''}actions</h3>
          <p>
            {filter === 'pending'
              ? 'All write operations have been reviewed. Ask the Copilot to make changes to see new items here.'
              : 'No write actions have been proposed yet. Try asking the Copilot to update a membership or user status.'}
          </p>
        </div>
      ) : (
        <div className="approval-list">
          {actions.map((action) => {
            const params = parseJson(action.params)
            const before = parseJson(action.before_state)
            const after = parseJson(action.after_state)

            return (
              <div key={action.id} className="glass-card approval-card">
                <div className="approval-header">
                  <div>
                    <div className="approval-title">
                      🔧 {action.tool_name}
                    </div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                      {action.description}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span className={`status-badge ${action.status}`}>
                      {action.status}
                    </span>
                    <div className="approval-time">{formatTime(action.created_at)}</div>
                  </div>
                </div>

                {/* Parameters */}
                {params && (
                  <div style={{
                    padding: '10px 14px',
                    background: 'var(--bg-input)',
                    borderRadius: 'var(--radius-sm)',
                    fontFamily: "'Courier New', monospace",
                    fontSize: '0.78rem',
                    color: 'var(--text-secondary)',
                    marginBottom: 12,
                  }}>
                    {JSON.stringify(params, null, 2)}
                  </div>
                )}

                {/* Diff view */}
                {(before || after) && (
                  <div className="diff-view">
                    {before && (
                      <div className="diff-before">
                        <div className="diff-label">Before</div>
                        {Object.entries(before).map(([k, v]) => (
                          <div key={k}>{k}: {String(v)}</div>
                        ))}
                      </div>
                    )}
                    {after && (
                      <div className="diff-after">
                        <div className="diff-label">After</div>
                        {Object.entries(after).map(([k, v]) => (
                          <div key={k}>{k}: {String(v)}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Actions */}
                {action.status === 'pending' && (
                  <div className="approval-actions">
                    <button
                      className="btn btn-primary"
                      onClick={() => handleApprove(action.id)}
                    >
                      ✓ Approve
                    </button>
                    <button
                      className="btn btn-danger"
                      onClick={() => handleReject(action.id)}
                    >
                      ✕ Reject
                    </button>
                  </div>
                )}

                {/* Resolution info */}
                {action.resolved_at && (
                  <div style={{
                    marginTop: 12,
                    fontSize: '0.75rem',
                    color: 'var(--text-muted)',
                  }}>
                    {action.status === 'approved' ? 'Approved' : 'Rejected'} at{' '}
                    {formatTime(action.resolved_at)}
                    {action.resolved_by && ` by ${action.resolved_by}`}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}
