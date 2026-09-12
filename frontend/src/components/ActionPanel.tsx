import { useEffect, useState } from 'react'
import type { Analysis, ApplyRequest, Dictionaries, OutboxLetter, Ticket } from '../types'
import { StatusBadge, dictLabel } from './Badge'
import { Section } from './Section'

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
        <div className="verdict" style={{ marginBottom: 8 }}>
          <span className="dot ok" />
          <b>Решение принято</b>
        </div>
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
      <div className="verdict">
        <span className="dot warn" />
        <b>{ACTION_TITLE[analysis.suggested_action ?? ''] ?? 'Предложенное действие'}</b>
      </div>

      {ticket && (
        <>
          <div className="facts">
            <span><b>{ticket.key}</b>{ticket.title}</span>
            <StatusBadge code={ticket.status} items={dicts?.ticket_statuses} />
          </div>

          <Section plain title="Текст заявки">
            <div className="letter-body">{ticket.description}</div>
          </Section>

          <Section
            plain
            title="Изменить параметры"
            meta={`${priority} · ${dictLabel(dicts?.teams, team)}`}
          >
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
                  {dicts?.teams.map((item) => (
                    <option key={item.code} value={item.code}>{item.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="field">
              <label>Категория</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                {dicts?.categories.map((c) => (
                  <option key={c.code} value={c.code}>{c.label}</option>
                ))}
              </select>
            </div>
          </Section>
        </>
      )}

      {letter && (
        <>
          <div className="facts">
            <span><b>{letter.kind === 'reply' ? 'Ответ' : 'Уточнение'}</b>{letter.subject}</span>
          </div>
          <textarea
            rows={Math.min(16, Math.max(7, body.split('\n').length + 1))}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            style={{ marginTop: 10 }}
          />
        </>
      )}

      <div className="btn-row actions" style={{ marginTop: 14 }}>
        <button
          className="btn btn-primary btn-lg"
          disabled={busy}
          onClick={() => apply(changed ? 'edit' : 'confirm')}
        >
          {changed ? 'Сохранить и подтвердить' : 'Подтвердить'}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={() => apply('reject')}>
          Отклонить
        </button>
        {changed && <span className="step-ms">есть правки</span>}
      </div>
    </div>
  )
}
