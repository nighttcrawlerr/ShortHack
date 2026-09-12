import { useCallback, useEffect, useState } from 'react'
import * as api from '../api/client'
import type { Dictionaries, Ticket } from '../types'
import { PriorityBadge, dictLabel } from '../components/Badge'

export function TicketsPage({ dicts }: { dicts?: Dictionaries }) {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setTickets(await api.getTickets({
      status: status || undefined,
      priority: priority || undefined,
      q: search || undefined,
    }))
  }, [status, priority, search])

  useEffect(() => { void load() }, [load])

  const change = async (ticket: Ticket, next: string) => {
    await api.patchTicket(ticket.id, { status: next })
    await load()
  }

  return (
    <div className="page">
      <div>
        <div className="section-title">Заявки</div>
        <div className="hint">
          Заявки со статусом «предложена агентом» ждут подтверждения оператора
        </div>
      </div>

      <div className="filters" style={{ maxWidth: 720 }}>
        <input type="search" placeholder="Поиск" value={search}
               onChange={(e) => setSearch(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Все статусы</option>
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

      <table className="table">
        <thead>
          <tr>
            <th>Номер</th><th>Заголовок</th><th>Категория</th><th>Приоритет</th>
            <th>Команда</th><th>Статус</th><th>Кем создана</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => (
            <tr key={ticket.id} className={ticket.status === 'proposed' ? 'proposed' : ''}>
              <td><b>{ticket.key}</b></td>
              <td>
                {ticket.title}
                {ticket.resolution && (
                  <div className="claim-note">{ticket.resolution}</div>
                )}
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
          ))}
        </tbody>
      </table>

      {!tickets.length && <div className="empty"><div>Заявок не найдено</div></div>}
    </div>
  )
}
