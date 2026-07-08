import { useState, useEffect } from 'react'
import { api } from '../api'

const FILTERS = [
  { key: null,        label: 'All' },
  { key: 'read',      label: '📖 Read' },
  { key: 'write',     label: '✏️ Write' },
  { key: 'approval',  label: '✅ Approval' },
]

export default function AuditLog({ activePage }) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState(null)
  const [expandedId, setExpandedId] = useState(null)

  const load = async () => {
    try {
      const data = await api.getAuditLogs(filter)
      setLogs(Array.isArray(data) ? data : [])
    } catch (err) {
      console.error('Failed to load audit logs:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setLoading(true)
    load()
  }, [filter])

  useEffect(() => {
    if (activePage === 'audit') {
      load()
    }
  }, [activePage])

  const formatTime = (ts) => {
    if (!ts) return ''
    return new Date(ts).toLocaleString('en-IN', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  const getActionIcon = (type) => {
    switch (type) {
      case 'read':     return '📖'
      case 'write':    return '✏️'
      case 'approval': return '✅'
      default:         return '📋'
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Audit Log</h1>
        <p>Complete trail of all Copilot actions and tool calls</p>
      </div>

      <div className="audit-filters">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            className={`filter-btn${filter === f.key ? ' active' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-spinner" />
      ) : logs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>No audit entries yet</h3>
          <p>
            Start interacting with the Copilot to see actions logged here.
            Every tool call is recorded with full parameters and results.
          </p>
        </div>
      ) : (
        <div className="audit-list">
          {logs.map((log) => (
            <div
              key={log.id}
              className="audit-entry"
              onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
            >
              <div className="audit-entry-header">
                <div className="audit-tool-name">
                  {getActionIcon(log.action_type)}
                  {log.tool_name || log.action_type}
                  <span className={`status-badge ${log.action_type === 'write' ? 'pending' : 'approved'}`}
                    style={{ fontSize: '0.65rem', padding: '2px 8px' }}>
                    {log.action_type}
                  </span>
                </div>
                <span className="audit-timestamp">{formatTime(log.timestamp)}</span>
              </div>

              {log.vendor_id && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Vendor: {log.vendor_id}
                  {log.affected_user_id && ` • User: ${log.affected_user_id}`}
                  {log.approved_by && ` • Approved by: ${log.approved_by}`}
                </div>
              )}

              {expandedId === log.id && (
                <div className="audit-details">
                  {log.params && (
                    <>
                      <strong>Parameters:</strong>
                      {'\n'}
                      {typeof log.params === 'object'
                        ? JSON.stringify(log.params, null, 2)
                        : log.params}
                    </>
                  )}
                  {log.result && (
                    <>
                      {'\n\n'}
                      <strong>Result:</strong>
                      {'\n'}
                      {typeof log.result === 'object'
                        ? JSON.stringify(log.result, null, 2)
                        : log.result}
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  )
}
