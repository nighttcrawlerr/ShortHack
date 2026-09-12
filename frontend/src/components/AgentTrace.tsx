import { useState } from 'react'
import type { AgentStep } from '../types'

const FALLBACK: Record<string, string> = {
  extract_structure: 'Разбор обращения моделью',
  search_similar_tickets: 'Поиск похожих заявок',
  search_knowledge_base: 'Поиск по базе знаний',
  decide_action: 'Выбор действия моделью',
  compose_answer: 'Написание ответа по источникам',
  verify_answer: 'Проверка ответа на искажения',
  create_ticket: 'Создание заявки',
  ask_clarification: 'Подготовка уточнения',
  draft_reply: 'Подготовка ответа',
  guard: 'Защита: ответ не отправлен',
  error: 'Ошибка прогона',
}

export function AgentTrace({ steps, names }: {
  steps: AgentStep[]; names?: Record<string, string>
}) {
  const [open, setOpen] = useState<number | null>(null)
  if (!steps.length) return null

  const llmCount = steps.filter((s) => s.kind === 'llm').length
  const total = steps.reduce((sum, s) => sum + s.latency_ms, 0)

  return (
    <div className="card">
      <div className="card-title">Как агент пришёл к решению</div>
      <div className="trace">
        {steps.map((step) => (
          <div
            key={step.step_no}
            className={`step ${step.kind}`}
            onClick={() => setOpen(open === step.step_no ? null : step.step_no)}
          >
            <div className="step-no">{step.step_no}</div>
            <div className="step-main">
              <div className="step-name">
                {step.kind === 'llm' ? '◆ ' : '⚙ '}
                {names?.[step.name] ?? FALLBACK[step.name] ?? step.name}
              </div>
              <div className="step-out">{step.output_preview}</div>
              {open === step.step_no && (
                <div className="step-detail">
                  <b>вход:</b> {step.input_preview || '—'}
                  {'\n\n'}
                  <b>выход:</b> {step.output_preview || '—'}
                </div>
              )}
            </div>
            <div className="step-ms">{step.latency_ms} мс</div>
          </div>
        ))}
      </div>
      <div className="hint" style={{ marginTop: 10 }}>
        Всего {steps.length} шагов, обращений к модели {llmCount}, суммарно {total} мс.
        Остальное сделал обычный код.
      </div>
    </div>
  )
}
