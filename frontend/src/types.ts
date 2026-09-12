export type Channel = 'email' | 'call'

export interface DictItem { code: string; label: string }

export interface Dictionaries {
  categories: DictItem[]
  priorities: DictItem[]
  teams: DictItem[]
  actions: DictItem[]
  sentiments: DictItem[]
  channels: DictItem[]
  message_statuses: DictItem[]
  ticket_statuses: DictItem[]
  step_names: Record<string, string>
}

export interface Health {
  status: string
  llm: 'live' | 'mock' | 'error'
  model: string
  llm_note: string | null
  retrieval: string
  embedder: string
  kb_chunks: number
  db_messages: number
}

export interface MessageListItem {
  id: number
  channel: Channel
  subject: string | null
  author_name: string
  author_email: string
  received_at: string
  preview: string
  status: string
  has_analysis: boolean
  category: string | null
  priority: string | null
  suggested_action: string | null
  auto_sent: boolean
  needs_human: boolean
}

export interface Message {
  id: number
  channel: Channel
  subject: string | null
  author_name: string
  author_email: string
  received_at: string
  body: string
  status: string
}

export interface MissingField { field: string; why: string; question: string }

export interface Passage {
  chunk_id: number
  article_id: number
  title: string
  text: string
  category: string
  service: string
  source: string
  score: number
  lexical_rank: number | null
  dense_rank: number | null
  matched_terms: string[]
}

export interface VerificationIssue {
  kind: string
  severity: 'critical' | 'warning'
  fragment: string
  explanation: string
}

export interface VerificationClaim {
  text: string
  verdict: 'supported' | 'contradicted' | 'not_found'
  source: number | null
  comment: string
}

export interface Verification {
  status: 'verified' | 'needs_review' | 'rejected' | 'insufficient'
  score: number
  checks: Record<string, unknown>
  issues: VerificationIssue[]
  claims: VerificationClaim[]
  model_used: boolean
  latency_ms: number
}

export interface Analysis {
  id: number
  message_id: number
  summary: string
  intents: string[]
  category: string
  service: string
  priority: string
  priority_reason: string
  team: string
  entities: Record<string, string>
  missing_fields: MissingField[]
  sentiment: string
  confidence: number
  suggested_action: string | null
  action_reason: string
  similar_ticket_ids: number[]
  kb_article_ids: number[]
  mass_incident: boolean
  passages: Passage[]
  verification: Verification | null
  retrieval_mode: string
  auto_sent: boolean
  human_reason: string
  model: string
  latency_ms: number
  created_at: string
}

export interface Ticket {
  id: number
  key: string
  message_id: number | null
  title: string
  description: string
  category: string
  service: string
  priority: string
  team: string
  status: string
  requester_name: string
  requester_email: string
  entities: Record<string, string>
  resolution: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface AgentStep {
  step_no: number
  kind: 'llm' | 'tool'
  name: string
  input_preview: string
  output_preview: string
  latency_ms: number
}

export interface OutboxLetter {
  id: number
  message_id: number
  ticket_id: number | null
  kind: 'clarification' | 'reply'
  subject: string
  body: string
  questions: string[]
  sources: Passage[]
  verification: Verification | null
  status: 'draft' | 'sent'
  created_at: string
}

export interface MessageDetail {
  message: Message
  analysis: Analysis | null
  steps: AgentStep[]
  tickets: Ticket[]
  outbox: OutboxLetter[]
}

export interface SimilarTicket {
  id: number
  key: string
  title: string
  status: string
  resolution: string | null
  score: number
}

export interface CountItem { code: string; label: string; count: number }

export interface MassIncident {
  category: string
  service: string
  count: number
  message_ids: number[]
  hint: string
}

export interface Stats {
  messages_total: number
  messages_analyzed: number
  tickets_total: number
  auto_actionable_share: number
  avg_latency_ms: number
  by_category: CountItem[]
  by_priority: CountItem[]
  by_action: CountItem[]
  mass_incidents: MassIncident[]
}

export interface RagResponse {
  query: string
  mode: string
  embedder: string
  hits: Passage[]
}

export interface ApplyRequest {
  decision: 'confirm' | 'edit' | 'reject'
  ticket_id?: number | null
  outbox_id?: number | null
  overrides?: Record<string, string> | null
  edited_body?: string | null
  edited_subject?: string | null
}

export type PortalStatus = 'answered' | 'ticket_created' | 'clarification' | 'pending_human'

export interface PortalSource { title: string; source: string }

export interface PortalReply {
  message_id: number
  status: PortalStatus
  reply: string
  questions: string[]
  sources: PortalSource[]
  ticket_key: string | null
  elapsed_ms: number
}
