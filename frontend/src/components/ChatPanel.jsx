import { useState, useRef, useEffect } from 'react'
import { api } from '../api'
import { renderMarkdown } from '../markdown'

const SUGGESTED_QUERIES = [
  "What is today's revenue?",
  "List trial users of badminton",
  "Show booking stats",
  "Membership summary",
  "Show me Rahul's details",
  "Extend Priya's trial by 7 days",
]

export default function ChatPanel({ activePage }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(scrollToBottom, [messages])

  const sendMessage = async (text) => {
    if (!text.trim() || loading) return

    const userMsg = { role: 'user', content: text.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const result = await api.chat(text.trim(), conversationId)

      if (result.conversation_id) {
        setConversationId(result.conversation_id)
      }

      // Build the assistant message with tool call info
      const assistantMsg = {
        role: 'assistant',
        content: result.response,
        toolCalls: result.tool_calls || [],
        pendingActions: result.pending_actions || [],
        blocked: result.blocked || false,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ Error: ${err.message}. Make sure the backend is running.`,
          toolCalls: [],
          pendingActions: [],
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const handleApprove = async (actionId, msgIndex) => {
    try {
      await api.approve(actionId)
      setMessages(prev =>
        prev.map((msg, i) => {
          if (i !== msgIndex) return msg
          return {
            ...msg,
            pendingActions: msg.pendingActions.map(a =>
              a.id === actionId ? { ...a, status: 'approved' } : a
            ),
          }
        })
      )
    } catch (err) {
      alert('Approve failed: ' + err.message)
    }
  }

  const handleReject = async (actionId, msgIndex) => {
    try {
      await api.reject(actionId)
      setMessages(prev =>
        prev.map((msg, i) => {
          if (i !== msgIndex) return msg
          return {
            ...msg,
            pendingActions: msg.pendingActions.map(a =>
              a.id === actionId ? { ...a, status: 'rejected' } : a
            ),
          }
        })
      )
    } catch (err) {
      alert('Reject failed: ' + err.message)
    }
  }

  return (
    <div className="chat-container">
      <div className="page-header">
        <h1>🤖 AI Copilot</h1>
        <p>Ask anything about your users, revenue, bookings, and memberships</p>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-screen">
            <div className="welcome-icon">🤖</div>
            <h2>Welcome to HobbyFi Copilot</h2>
            <p>
              I can help you manage your CRM data — query revenue, list users,
              check bookings, and even update records with your approval.
            </p>
            <div className="suggested-queries">
              {SUGGESTED_QUERIES.map((q, i) => (
                <button
                  key={i}
                  className="query-chip"
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-avatar">
              {msg.role === 'assistant' ? 'H' : 'V'}
            </div>
            <div className="chat-bubble">
              {/* Tool calls */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div>
                  {msg.toolCalls.map((tc, j) => (
                    <div key={j} className="tool-call-card">
                      <div className="tool-name">
                        🔧 {tc.name}
                        <span className={`tool-call-badge ${tc.access_level}`}>
                          {tc.access_level}
                        </span>
                      </div>
                      {tc.arguments && Object.keys(tc.arguments).length > 0 && (
                        <div className="tool-args">
                          {JSON.stringify(tc.arguments, null, 2)}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Message text — render markdown for assistant, plain for user */}
              {msg.role === 'assistant' ? (
                <div
                  className="md-content"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                />
              ) : (
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
              )}

              {/* Pending approval actions */}
              {msg.pendingActions && msg.pendingActions.length > 0 && (
                <div>
                  {msg.pendingActions.map((action, j) => (
                    <div key={j} className="pending-action-card">
                      <h4>
                        ⏳ Pending Approval
                        {action.status && action.status !== 'pending' && (
                          <span className={`status-badge ${action.status}`} style={{ marginLeft: 8 }}>
                            {action.status}
                          </span>
                        )}
                      </h4>
                      <div className="action-desc">{action.description}</div>
                      {action.before_state && (
                        <div className="diff-view">
                          <div className="diff-before">
                            <div className="diff-label">Before</div>
                            {Object.entries(action.before_state).map(([k, v]) => (
                              <div key={k}>{k}: {String(v)}</div>
                            ))}
                          </div>
                          <div className="diff-after">
                            <div className="diff-label">After (proposed)</div>
                            {action.after_state ? (
                              Object.entries(action.after_state).map(([k, v]) => (
                                <div key={k}>{k}: {String(v)}</div>
                              ))
                            ) : (
                              <div style={{ color: 'var(--text-muted)' }}>
                                Changes as described above
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      {(!action.status || action.status === 'pending') && (
                        <div className="action-buttons">
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleApprove(action.id, i)}
                          >
                            ✓ Approve
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            onClick={() => handleReject(action.id, i)}
                          >
                            ✕ Reject
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-message assistant">
            <div className="chat-avatar">H</div>
            <div className="chat-bubble">
              <div className="typing-indicator">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        {messages.length > 0 && (
          <div className="suggested-queries">
            {SUGGESTED_QUERIES.slice(0, 3).map((q, i) => (
              <button key={i} className="query-chip" onClick={() => sendMessage(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
        <div className="chat-input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask the Copilot anything..."
            rows={1}
            disabled={loading}
          />
          <button
            className="btn btn-primary btn-icon"
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
            title="Send"
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  )
}
