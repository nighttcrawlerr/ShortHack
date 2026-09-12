import { useEffect, useState } from 'react'
import type { Analysis, ApplyRequest, Dictionaries, OutboxLetter, Ticket } from '../types'
import { StatusBadge, dictLabel } from './Badge'

const ACTION_TITLE: Record<string, string> = {
  create_ticket: 'Агент создал заявку',
  ask_clarification: 'Агент подготовил уточняющее письмо',
  draft_reply: 'Агент подготовил ответ пользователю',
}

export function ActionPanel({ analysis, tickets, outbox, dicts, busy, onApply }: {
  analysis: Analysis
  tickets: Ticket[]
  outbox: OutboxLetter[]
  dicts?: Dictionaries
  busy: boolean
  onApply: (payload: ApplyRequest) => void
}) {
  const ticket = tickets.find((t) => t.status === 'proposed') ?? null
  const letter = outbox.find((o) => o.status === 'draft') ?? null
  const settled = !ticket && !letter

  const [priority, setPriority] = useState('')
  const [category, setCategory] = useState('')
  const [team, setTeam] = useState('')
  const [body, setBody] = useState('')

  useEffect(() => {
    setPriority(ticket?.priority ?? '')
    setCategory(ticket?.category ?? '')
    setTeam(ticket?.team ?? '')
    setBody(letter?.body ?? '')
  }, [ticket?.id, letter?.id, ticket?.priority, ticket?.category, ticket?.team, letter?.body])

  if (settled) {
    const done = [...tickets, ...outbox]
    if (!done.length) return null
    return (
      <div className="card">
        <div className="card-title">Решение принято</div>
        {tickets.map((t) => (
          <div key={t.id} className="meta" style={{ marginBottom: 6 }}>
            <b>{t.key}</b>
            <StatusBadge code={t.status} items={dicts?.ticket_statuses} />
            <span>{t.title}</span>
          </div>
        ))}
        {outbox.map((o) => (
          <div key={o.id} className="meta">
            <span>{o.kind === 'reply' ? 'Ответ' : 'Уточнение'}</span>
            <span className="badge ok">{o.status === 'sent' ? 'отправлено' : 'черновик'}</span>
            <span>{o.subject}</span>
          </div>
        ))}
      </div>
    )
  }

  const changed =
    (!!ticket &&
      (priority !== ticket.priority || category !== ticket.category || team !== ticket.team)) ||
    (!!letter && body !== letter.body)

  const apply = (decision: 'confirm' | 'edit' | 'reject') => {
    const payload: ApplyRequest = { decision }
    if (decision === 'edit') {
      if (ticket) payload.overrides = { priority, category, team }
      if (letter) payload.edited_body = body
    }
    onApply(payload)
  }

  return (
    <div className="card">
      <div className="card-title">
        {ACTION_TITLE[analysis.suggested_action ?? ''] ?? 'Предложенное действие'}
      </div>

      {analysis.action_reason && (
        <div className="notice info" style={{ marginBottom: 12 }}>
          <b>Почему так.</b> {analysis.action_reason}
        </div>
      )}

      {ticket && (
        <>
          <div className="meta" style={{ marginBottom: 8 }}>
            <b style={{ fontSize: 16 }}>{ticket.key}</b>
            <StatusBadge code={ticket.status} items={dicts?.ticket_statuses} />
          </div>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>{ticket.title}</div>
          <div className="letter-body" style={{ color: 'var(--muted)', marginBottom: 12 }}>
            {ticket.description}
          </div>

          <div className="field-row" style={{ marginBottom: 10 }}>
            <div className="field">
              <label>Приоритет</label>
              <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                {dicts?.priorities.map((p) => (
                  <option key={p.code} value={p.code}>{p.code} · {p.label}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Команда</label>
              <select value={team} onChange={(e) => setTeam(e.target.value)}>
                {dicts?.teams.map((t) => (
                  <option key={t.code} value={t.code}>{t.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="field" style={{ marginBottom: 12 }}>
            <label>Категория</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {dicts?.categories.map((c) => (
                <option key={c.code} value={c.code}>{c.label}</option>
              ))}
            </select>
          </div>
        </>
      )}

      {letter && (
        <>
          <div className="meta" style={{ marginBottom: 8 }}>
            <b>{letter.subject}</b>
            <span className="badge">
              {letter.kind === 'reply' ? 'ответ пользователю' : 'уточняющие вопросы'}
            </span>
          </div>
          <textarea
            rows={Math.min(18, Math.max(8, body.split('\n').length + 1))}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            style={{ marginBottom: 12 }}
          />
        </>
      )}

      <div className="notice info" style={{ marginBottom: 12 }}>
        Ничего не уходит пользователю, пока вы не подтвердите. Агент только подготовил.
      </div>

      <div className="btn-row">
        <button
          className="btn btn-primary"
          disabled={busy}
          onClick={() => apply(changed ? 'edit' : 'confirm')}
        >
          {changed ? 'Сохранить и подтвердить' : 'Подтвердить'}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={() => apply('reject')}>
          Отклонить
        </button>
        {changed && <span className="step-ms" style={{ alignSelf: 'center' }}>есть правки</span>}
      </div>

      {ticket && (
        <div className="hint" style={{ marginTop: 8 }}>
          Ответственная команда: {dictLabel(dicts?.teams, team)}
        </div>
      )}
    </div>
  )
}
