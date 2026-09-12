import type { Analysis, Dictionaries, OutboxLetter, Ticket } from '../types'
import { StatusBadge, dictLabel } from './Badge'
import { Section } from './Section'

const ACTION_SENT: Record<string, string> = {
  create_ticket: 'Заявка заведена и передана в работу',
  ask_clarification: 'Уточняющее письмо отправлено',
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
      <div className="verdict">
        <span className="dot ok" />
        <b>{ACTION_SENT[action] ?? 'Действие выполнено'}</b>
        <span className="verdict-score">{seconds} с</span>
      </div>

      {tickets.map((ticket) => (
        <Section
          plain
          key={ticket.id}
          title={`${ticket.key} · ${ticket.title}`}
          meta={dictLabel(dicts?.teams, ticket.team)}
        >
          <div className="meta" style={{ marginBottom: 6 }}>
            <StatusBadge code={ticket.status} items={dicts?.ticket_statuses} />
          </div>
          <div className="letter-body">{ticket.description}</div>
        </Section>
      ))}

      {outbox.map((letter) => (
        <Section
          plain
          key={letter.id}
          title={letter.subject}
          meta={letter.status === 'sent' ? 'отправлено' : 'черновик'}
        >
          <div className="letter-body">{letter.body}</div>
        </Section>
      ))}
    </div>
  )
}
