import type { DictItem, SimilarTicket } from '../types'
import { StatusBadge } from './Badge'

export function SimilarList({ tickets, statuses }: {
  tickets: SimilarTicket[]; statuses?: DictItem[]
}) {
  if (!tickets.length) return null
  return (
    <div className="card">
      <div className="card-title">Похожие заявки и чем они закончились</div>
      {tickets.map((ticket) => (
        <div className="passage" key={ticket.id}>
          <div className="passage-head">
            <span className="passage-no">{ticket.key}</span>
            <span className="passage-title">{ticket.title}</span>
            <StatusBadge code={ticket.status} items={statuses} />
            <span className="badge">{Math.round(ticket.score * 100)}%</span>
          </div>
          {ticket.resolution && <div className="passage-text">{ticket.resolution}</div>}
        </div>
      ))}
    </div>
  )
}
