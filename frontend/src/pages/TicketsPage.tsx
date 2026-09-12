import { useCallback, useEffect, useState } from 'react'
import * as api from '../api/client'
import type { Dictionaries, Ticket } from '../types'
import { PriorityBadge, dictLabel } from '../components/Badge'
import { Section } from '../components/Section'

/** Заявка отработана: в рабочем списке ей делать нечего. */
const ARCHIVED = new Set(['closed', 'rejected'])

type Undo = { id: number; key: string; from: string }

export function TicketsPage({ dicts }: { dicts?: Dictionaries }) {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [search, setSearch] = useState('')
  const [leaving, setLeaving] = useState<number | null>(null)
  const [undo, setUndo] = useState<Undo | null>(null)

  const load = useCallback(async () => {
    setTickets(await api.getTickets({
      status: status || undefined,
      priority: priority || undefined,
      q: search || undefined,
    }))
  }, [status, priority, search])

  useEffect(() => { void load() }, [load])

  const change = async (ticket: Ticket, next: string) => {
    if (next === ticket.status) return
    await api.patchTicket(ticket.id, { status: next })

    // Уход в архив показываем: строка сначала проваливается, и только
    // потом список перечитывается. Иначе заявка исчезает без объяснений.
    if (ARCHIVED.has(next) && !ARCHIVED.has(ticket.status)) {
      setLeaving(ticket.id)
      setUndo({ id: ticket.id, key: ticket.key, from: ticket.status })
      setTimeout(() => { setLeaving(null); void load() }, 280)
      return
    }
    setUndo(null)
    await load()
  }

  const restore = async () => {
    if (!undo) return
    await api.patchTicket(undo.id, { status: undo.from })
    setUndo(null)
    await load()
  }

  const rows = (list: Ticket[]) => list.map((ticket) => (
    <tr
      key={ticket.id}
      className={`${ticket.status === 'proposed' ? 'proposed' : ''} ${
        leaving === ticket.id ? 'row-leaving' : ''
      }`}
    >
      <td><b>{ticket.key}</b></td>
      <td>
        {ticket.title}
        {ticket.resolution && <div className="claim-note">{ticket.resolution}</div>}
      </td>
      <td>{dictLabel(dicts?.categories, ticket.category)}</td>
      <td><PriorityBadge code={ticket.priority} items={dicts?.priorities} /></td>
      <td>{dictLabel(dicts?.teams, ticket.team)}</td>
      <td>
        <select value={ticket.status} onChange={(e) => change(ticket, e.target.value)}>
          {dicts?.ticket_statuses.map((s) => (
            <option key={s.code} value={s.code}>{s.label}</option>
          ))}
        </select>
      </td>
      <td>{ticket.created_by === 'agent' ? 'Агент' : 'Оператор'}</td>
    </tr>
  ))

  const table = (list: Ticket[]) => (
    <table className="table">
      <thead>
        <tr>
          <th>Номер</th><th>Заголовок</th><th>Категория</th><th>Приоритет</th>
          <th>Команда</th><th>Статус</th><th>Кем создана</th>
        </tr>
      </thead>
      <tbody>{rows(list)}</tbody>
    </table>
  )

  const filtered = Boolean(status)
  const active = filtered ? tickets : tickets.filter((t) => !ARCHIVED.has(t.status))
  const archive = filtered ? [] : tickets
    .filter((t) => ARCHIVED.has(t.status))
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))

  return (
    <div className="page">
      <div className="section-title">Заявки</div>

      <div className="filters" style={{ maxWidth: 720 }}>
        <input type="search" placeholder="Поиск" value={search}
               onChange={(e) => setSearch(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">В работе и архив раздельно</option>
          {dicts?.ticket_statuses.map((s) => (
            <option key={s.code} value={s.code}>{s.label}</option>
          ))}
        </select>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">Все приоритеты</option>
          {dicts?.priorities.map((p) => (
            <option key={p.code} value={p.code}>{p.code} · {p.label}</option>
          ))}
        </select>
      </div>

      {undo && (
        <div className="notice ok undo-bar">
          <span>{undo.key} ушла в архив</span>
          <button className="btn btn-sm" onClick={restore}>Вернуть</button>
        </div>
      )}

      {active.length > 0 && table(active)}
      {!active.length && (
        <div className="empty">
          <div>{filtered ? 'Заявок не найдено' : 'В работе пусто'}</div>
        </div>
      )}

      {archive.length > 0 && (
        <Section title="Архив" meta={`${archive.length} закрыто и отклонено`}>
          {table(archive)}
        </Section>
      )}
    </div>
  )
}
