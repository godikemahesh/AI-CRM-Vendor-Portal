import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Dashboard({ activePage }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const d = await api.dashboard()
      setData(d)
    } catch (err) {
      console.error('Dashboard load error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (activePage === 'dashboard') {
      load()
    }
  }, [activePage])

  if (loading) return <div className="loading-spinner" />

  if (!data) {
    return (
      <div className="empty-state">
        <div className="empty-icon">⚠️</div>
        <h3>Unable to load dashboard</h3>
        <p>Make sure the backend server is running on port 8000.</p>
      </div>
    )
  }

  const kpis = [
    { icon: '💰', label: "Today's Revenue", value: `₹${Number(data.today_revenue).toLocaleString('en-IN')}`, trend: '+12%', up: true },
    { icon: '👥', label: 'Active Users', value: data.active_users, trend: '+3', up: true },
    { icon: '🎯', label: 'Trial Users', value: data.trial_users, trend: 'Active', up: true },
    { icon: '📅', label: 'Bookings (30d)', value: data.total_bookings, trend: '+8%', up: true },
  ]

  // Build chart data from revenue_trend
  const trend = data.revenue_trend || []
  const maxRev = Math.max(...trend.map(t => t.revenue), 1)

  // Membership donut data
  const memberTypes = data.membership_breakdown || []
  const totalMembers = memberTypes.reduce((s, m) => s + m.count, 0)
  const donutColors = ['#22c55e', '#3b82f6', '#f59e0b', '#8b5cf6']

  // Build conic-gradient for donut
  let conicParts = []
  let cumPercent = 0
  memberTypes.forEach((m, i) => {
    const pct = totalMembers > 0 ? (m.count / totalMembers) * 100 : 0
    conicParts.push(`${donutColors[i % donutColors.length]} ${cumPercent}% ${cumPercent + pct}%`)
    cumPercent += pct
  })
  const conicGradient = `conic-gradient(${conicParts.join(', ')})`

  return (
    <>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Overview of your HobbyFi centre performance</p>
      </div>

      {/* KPI Grid */}
      <div className="kpi-grid">
        {kpis.map((kpi, i) => (
          <div key={i} className="glass-card kpi-card">
            <div className="kpi-icon">{kpi.icon}</div>
            <div className="kpi-label">{kpi.label}</div>
            <div className="kpi-value">{kpi.value}</div>
            <div className={`kpi-trend ${kpi.up ? 'up' : 'down'}`}>
              {kpi.up ? '↑' : '↓'} {kpi.trend}
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="charts-grid">
        {/* Revenue Trend */}
        <div className="glass-card chart-card">
          <h3>Revenue Trend (Last 7 Days)</h3>
          <div className="mini-chart">
            {trend.map((t, i) => {
              const height = maxRev > 0 ? Math.max((t.revenue / maxRev) * 100, 4) : 4
              const dayLabel = new Date(t.day + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short' })
              return (
                <div key={i} className="bar-wrapper">
                  <div
                    className="bar"
                    style={{ height: `${height}%` }}
                    title={`₹${Number(t.revenue).toLocaleString('en-IN')}`}
                  />
                  <span className="bar-label">{dayLabel}</span>
                </div>
              )
            })}
            {trend.length === 0 && (
              <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 'auto' }}>
                No revenue data yet
              </span>
            )}
          </div>
        </div>

        {/* Membership Breakdown */}
        <div className="glass-card chart-card">
          <h3>Memberships</h3>
          <div className="donut-container">
            <div
              className="donut"
              style={{ background: totalMembers > 0 ? conicGradient : 'var(--bg-hover)' }}
            >
              <div className="donut-center">{totalMembers}</div>
            </div>
            <div className="donut-legend">
              {memberTypes.map((m, i) => (
                <div key={m.type} className="donut-legend-item">
                  <span
                    className="donut-legend-dot"
                    style={{ background: donutColors[i % donutColors.length] }}
                  />
                  <span>{m.type}: {m.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="glass-card chart-card">
        <h3>Recent Agent Activity</h3>
        {data.recent_activity && data.recent_activity.length > 0 ? (
          <div className="activity-feed">
            {data.recent_activity.map((act, i) => (
              <div key={i} className="activity-item">
                <span className={`activity-dot ${act.action_type}`} />
                <div>
                  <div className="activity-text">
                    <strong>{act.tool_name || act.action_type}</strong>
                    {' — '}
                    {act.action_type} operation
                  </div>
                  <div className="activity-time">
                    {act.timestamp ? new Date(act.timestamp).toLocaleString('en-IN') : ''}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state" style={{ padding: '30px 20px' }}>
            <p>No activity yet. Start chatting with the Copilot!</p>
          </div>
        )}
      </div>
    </>
  )
}
