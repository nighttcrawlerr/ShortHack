import type {
  Analysis, ApplyRequest, Dictionaries, DictItem, Health, MessageDetail, MessageListItem,
  PortalReply, PortalTurn, RagResponse, SimilarTicket, Stats, Ticket,
} from '../types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    let detail = `Ошибка ${response.status}`
    try {
      const payload = await response.json()
      if (payload?.detail) detail = String(payload.detail)
    } catch { /* тело может быть пустым */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

const query = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const getHealth = () => request<Health>('/health')
export const getDictionaries = () => request<Dictionaries>('/dictionaries')

export const getMessages = (params: { status?: string; q?: string } = {}) =>
  request<MessageListItem[]>(`/messages${query(params)}`)

export const getMessage = (id: number) => request<MessageDetail>(`/messages/${id}`)

export const createMessage = (body: {
  channel: string; subject?: string; author_name?: string
  author_email?: string; body: string
}) => request<{ id: number }>('/messages', { method: 'POST', body: JSON.stringify(body) })

export const analyzeMessage = (id: number, force = false) =>
  request<MessageDetail>(`/messages/${id}/analyze${force ? '?force=true' : ''}`, { method: 'POST' })

export const applyDecision = (id: number, payload: ApplyRequest) =>
  request<MessageDetail>(`/messages/${id}/apply`, { method: 'POST', body: JSON.stringify(payload) })

export const getTickets = (params: {
  status?: string; category?: string; priority?: string; q?: string
} = {}) => request<Ticket[]>(`/tickets${query(params)}`)

export const patchTicket = (id: number, payload: Partial<Ticket>) =>
  request<Ticket>(`/tickets/${id}`, { method: 'PATCH', body: JSON.stringify(payload) })

export const getSimilar = (messageId: number) =>
  request<SimilarTicket[]>(`/similar${query({ message_id: messageId })}`)

export const searchRag = (q: string, limit = 5) =>
  request<RagResponse>(`/rag${query({ q, limit })}`)

export const analyzeAll = () =>
  request<{ analyzed: number; failed: number }>('/messages/analyze-all', { method: 'POST' })

export const getPortalCategories = () =>
  request<{ categories: DictItem[]; greeting: string }>('/portal/categories')

export const portalAsk = (payload: {
  text: string; category?: string | null; message_id?: number | null
}) => request<PortalReply>('/portal/ask', { method: 'POST', body: JSON.stringify(payload) })

export const getPortalThread = (messageId: number) =>
  request<PortalTurn[]>(`/portal/thread/${messageId}`)

export const getStats = () => request<Stats>('/stats')
export const reseed = () => request<Record<string, number>>('/seed', { method: 'POST' })

export type { Analysis }
