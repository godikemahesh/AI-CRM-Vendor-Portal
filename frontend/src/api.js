/**
 * API client — all backend calls go through here.
 * Uses VITE_API_URL when provided, otherwise falls back to the Vite dev proxy.
 */

const BASE = import.meta.env.VITE_API_URL || '';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  // Chat
  chat: (message, conversationId) =>
    request('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId }),
    }),

  // Dashboard
  dashboard: () => request('/api/dashboard'),

  // Approvals
  getApprovals: (status) =>
    request(`/api/approvals${status ? `?status=${status}` : ''}`),
  approve: (actionId) =>
    request(`/api/approvals/${actionId}/approve`, { method: 'POST', body: '{}' }),
  reject: (actionId) =>
    request(`/api/approvals/${actionId}/reject`, { method: 'POST', body: '{}' }),

  // Audit
  getAuditLogs: (actionType, limit = 50) => {
    const params = new URLSearchParams();
    if (actionType) params.set('action_type', actionType);
    params.set('limit', String(limit));
    return request(`/api/audit?${params}`);
  },
};
