import { useCallback, useEffect, useState } from 'react'
import * as api from '../api/client'
import type {
  ApplyRequest, Dictionaries, MessageDetail, MessageListItem, SimilarTicket,
} from '../types'
import { ActionPanel } from '../components/ActionPanel'
import { Outcome } from '../components/Outcome'
import { AgentTrace } from '../components/AgentTrace'
import { AnalysisCard } from '../components/AnalysisCard'
import { CategoryBadge, ChannelBadge, PriorityBadge } from '../components/Badge'
import { NewMessageModal } from '../components/NewMessageModal'
import { Passages } from '../components/Passages'
import { SimilarList } from '../components/SimilarList'
import { VerificationPanel } from '../components/Verification'

const time = (iso: string) => iso.slice(11, 16)

function Skeleton() {
  return (
    <div className="pane">
      <div className="skel" style={{ height: 92 }} />
      <div className="skel" style={{ height: 140 }} />
      <div className="skel" style={{ height: 180 }} />
    </div>
  )
}

export function InboxPage({ dicts, selected, onSelect, onChanged }: {
  dicts?: Dictionaries
  selected: number | null
  onSelect: (id: number | null) => void
  onChanged: () => void
}) {
  const [messages, setMessages] = useState<MessageListItem[]>([])
  const [detail, setDetail] = useState<MessageDetail | null>(null)
  const [similar, setSimilar] = useState<SimilarTicket[]>([])
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [bulk, setBulk] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [modal, setModal] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)

  const loadList = useCallback(async () => {
    try {
      setMessages(await api.getMessages({ q: search || undefined, status: status || undefined }))
    } catch (e) {
      setError((e as Error).message)
    }
  }, [search, status])

  useEffect(() => { void loadList() }, [loadList])

  useEffect(() => {
    if (selected === null) { setDetail(null); setSimilar([]); return }
    let alive = true
    setError(null)
    void (async () => {
      try {
        const data = await api.getMessage(selected)
        if (alive) setDetail(data)
        const hits = await api.getSimilar(selected)
        if (alive) setSimilar(hits)
      } catch (e) {
        if (alive) setError((e as Error).message)
      }
    })()
    return () => { alive = false }
  }, [selected])

  const analyze = async (force = false) => {
    if (selected === null) return
    setAnalyzing(true)
    setError(null)
    try {
      setDetail(await api.analyzeMessage(selected, force))
      await loadList()
      onChanged()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setAnalyzing(false)
    }
  }

  const apply = async (payload: ApplyRequest) => {
    if (selected === null) return
    setBusy(true)
    try {
      const updated = await api.applyDecision(selected, payload)
      setDetail(updated)
      const ticket = updated.tickets.find((t) => t.status === 'open' || t.status === 'waiting_user')
      setFlash(
        payload.decision === 'reject'
          ? 'Предложение отклонено, обращение вернулось в очередь'
          : ticket
            ? `Заявка ${ticket.key} передана в работу`
            : 'Письмо отправлено пользователю',
      )
      setTimeout(() => setFlash(null), 4000)
      await loadList()
      onChanged()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const create = async (payload: Parameters<typeof api.createMessage>[0]) => {
    setBusy(true)
    try {
      const created = await api.createMessage(payload)
      setModal(false)
      await loadList()
      onSelect(created.id)
      setAnalyzing(true)
      setDetail(await api.analyzeMessage(created.id))
      await loadList()
      onChanged()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
      setAnalyzing(false)
    }
  }

  const analysis = detail?.analysis ?? null
  const letter = detail?.outbox.find((o) => o.status === 'draft') ?? null
  const verification = letter?.verification ?? analysis?.verification ?? null

  return (
    <div className="inbox">
      <div className="column">
        <div className="column-head">
          <input
            type="search"
            placeholder="Поиск по обращениям"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="filters">
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">Все статусы</option>
              {dicts?.message_statuses.map((s) => (
                <option key={s.code} value={s.code}>{s.label}</option>
              ))}
            </select>
            <button className="btn btn-sm" onClick={() => setModal(true)}>Новое</button>
            <button
              className="btn btn-sm"
              title="Разобрать все необработанные обращения в очереди"
              disabled={bulk}
              onClick={async () => {
                setBulk(true)
                try { await api.analyzeAll(); await loadList(); onChanged() }
                catch (e) { setError((e as Error).message) }
                finally { setBulk(false) }
              }}
            >
              {bulk ? '…' : 'Разобрать все'}
            </button>
          </div>
        </div>

        {messages.map((message) => (
          <div
            key={message.id}
            className={`msg ${selected === message.id ? 'selected' : ''} ${
              message.status === 'processed' ? 'processed' : ''
            } ${message.needs_human ? 'needs-human' : ''}`}
            onClick={() => onSelect(message.id)}
          >
            <div className="msg-top">
              <ChannelBadge code={message.channel} />
              <span>{message.author_name}</span>
              <span style={{ marginLeft: 'auto' }}>{time(message.received_at)}</span>
            </div>
            <div className="msg-subject">
              {message.subject ?? `Звонок от ${message.author_name}`}
            </div>
            <div className="msg-preview">{message.preview}</div>
            {message.has_analysis && (
              <div className="msg-tags">
                <CategoryBadge code={message.category} items={dicts?.categories} />
                <PriorityBadge code={message.priority} items={dicts?.priorities} />
                {message.needs_human && <span className="badge warn">нужен человек</span>}
                {message.auto_sent && <span className="badge ok">отправлено</span>}
              </div>
            )}
          </div>
        ))}

        {!messages.length && (
          <div className="empty"><div>Ничего не найдено</div></div>
        )}
      </div>

      <div className="column">
        {!detail && (
          <div className="empty">
            <div style={{ fontSize: 32 }}>✉</div>
            <div>Выберите обращение слева</div>
          </div>
        )}
        {detail && (
          <div className="pane">
            <div className="card">
              <div className="meta" style={{ marginBottom: 8 }}>
                <ChannelBadge code={detail.message.channel} />
                <span>{detail.message.author_name} &lt;{detail.message.author_email}&gt;</span>
                <span style={{ marginLeft: 'auto' }}>
                  {detail.message.received_at.replace('T', ' ').slice(0, 16)}
                </span>
              </div>
              <div className="section-title" style={{ marginBottom: 10 }}>
                {detail.message.subject ?? `Расшифровка звонка от ${detail.message.author_name}`}
              </div>
              <div className="msg-body">{detail.message.body}</div>
            </div>

            <div className="btn-row">
              <button className="btn btn-primary" disabled={analyzing} onClick={() => analyze(false)}>
                {analyzing ? 'Разбираю…' : analysis ? 'Показать разбор' : 'Разобрать'}
              </button>
              {analysis && (
                <button className="btn btn-ghost" disabled={analyzing} onClick={() => analyze(true)}>
                  Разобрать заново
                </button>
              )}
            </div>

            {error && (
              <div className="notice bad">
                {error}
                <div className="btn-row" style={{ marginTop: 8 }}>
                  <button className="btn btn-sm" onClick={() => analyze(true)}>Повторить</button>
                </div>
              </div>
            )}

            <SimilarList tickets={similar} statuses={dicts?.ticket_statuses} />

            {analysis && analysis.passages.length > 0 && (
              <Passages passages={analysis.passages} mode={analysis.retrieval_mode} />
            )}
          </div>
        )}
      </div>

      <div className="column">
        {analyzing && <Skeleton />}
        {!analyzing && !analysis && (
          <div className="empty">
            <div style={{ fontSize: 32 }}>◆</div>
            <div>Нажмите «Разобрать», и здесь появится разбор</div>
          </div>
        )}
        {!analyzing && analysis && detail && (
          <div className="pane">
            {flash && <div className="notice ok">{flash}</div>}
            <AnalysisCard analysis={analysis} dicts={dicts} />
            {verification && <VerificationPanel verification={verification} />}
            {analysis.auto_sent ? (
              <Outcome
                analysis={analysis}
                tickets={detail.tickets}
                outbox={detail.outbox}
                dicts={dicts}
              />
            ) : (
              <>
                {analysis.human_reason && (
                  <div className="notice warn">
                    <b>Нужен человек.</b> {analysis.human_reason}. Отправка остановлена.
                  </div>
                )}
                <ActionPanel
                  analysis={analysis}
                  tickets={detail.tickets}
                  outbox={detail.outbox}
                  dicts={dicts}
                  busy={busy}
                  onApply={apply}
                />
              </>
            )}
            <AgentTrace steps={detail.steps} names={dicts?.step_names} />
          </div>
        )}
      </div>

      {modal && (
        <NewMessageModal busy={busy} onClose={() => setModal(false)} onCreate={create} />
      )}
    </div>
  )
}
