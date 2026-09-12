import type { Analysis, Dictionaries, OutboxLetter, Ticket } from '../types'
import { StatusBadge, dictLabel } from './Badge'

const ACTION_SENT: Record<string, string> = {
  create_ticket: 'Заявка заведена и передана в работу',
  ask_clarification: 'Уточняющее письмо отправлено пользователю',
  draft_reply: 'Ответ отправлен пользователю',
}

/**
 * Показывает, чем закончился разбор.
 *
 * Прошедший проверку ответ уходит сам: подтверждать каждое письмо человеком
 * слишком медленно, пользователь всё это время ждёт. Человек подключается
 * там, где проверка что-то нашла, и тогда вместо отчёта показывается
 * панель решения.
 */
export function Outcome({ analysis, tickets, outbox, dicts }: {
  analysis: Analysis
  tickets: Ticket[]
  outbox: OutboxLetter[]
  dicts?: Dictionaries
}) {
  const action = analysis.suggested_action ?? ''
  const seconds = (analysis.latency_ms / 1000).toFixed(1)

  return (
    <div className="card">
      <div className="card-title">Результат</div>

      <div className="notice ok" style={{ marginBottom: 12 }}>
        <b>{ACTION_SENT[action] ?? 'Действие выполнено'}</b>
        <div style={{ marginTop: 3 }}>
          Ответ прошёл проверку на искажения, поэтому ушёл без ожидания оператора.
          Весь разбор занял {seconds} с.
        </div>
      </div>

      {analysis.action_reason && (
        <div className="hint" style={{ marginBottom: 12 }}>
          Почему так: {analysis.action_reason}
        </div>
      )}

      {tickets.map((ticket) => (
        <div key={ticket.id} style={{ marginBottom: 10 }}>
          <div className="meta" style={{ marginBottom: 4 }}>
            <b style={{ fontSize: 15 }}>{ticket.key}</b>
            <StatusBadge code={ticket.status} items={dicts?.ticket_statuses} />
            <span className="badge">{dictLabel(dicts?.teams, ticket.team)}</span>
          </div>
          <div style={{ fontWeight: 600 }}>{ticket.title}</div>
          <div className="letter-body" style={{ color: 'var(--muted)', marginTop: 4 }}>
            {ticket.description}
          </div>
        </div>
      ))}

      {outbox.map((letter) => (
        <div key={letter.id} style={{ marginTop: 10 }}>
          <div className="meta" style={{ marginBottom: 6 }}>
            <b>{letter.subject}</b>
            <span className="badge ok">
              {letter.status === 'sent' ? 'отправлено' : 'черновик'}
            </span>
          </div>
          <div className="letter-body">{letter.body}</div>
        </div>
      ))}
    </div>
  )
}
