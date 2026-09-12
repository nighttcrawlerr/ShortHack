import type { Analysis, Dictionaries } from '../types'
import { CategoryBadge, PriorityBadge, dictLabel } from './Badge'
import { Section } from './Section'

const ENTITY_LABELS: Record<string, string> = {
  login: 'Логин',
  full_name: 'ФИО',
  email: 'Почта',
  phone: 'Телефон',
  employee_id: 'Табельный',
  service_name: 'Сервис',
  device: 'Устройство',
  os: 'ОС',
  browser: 'Браузер',
  error_code: 'Код ошибки',
  occurred_at: 'Когда',
  location: 'Где',
  inventory_number: 'Инвентарный',
}

export function AnalysisCard({ analysis, dicts }: {
  analysis: Analysis; dicts?: Dictionaries
}) {
  const entities = Object.entries(analysis.entities ?? {})
  const percent = Math.round(analysis.confidence * 100)

  return (
    <>
      {analysis.mass_incident && (
        <div className="notice warn">Возможен массовый сбой по этому сервису</div>
      )}

      <div className="card">
        <div className="headline">{analysis.summary}</div>

        <div className="msg-tags" style={{ marginTop: 10 }}>
          <CategoryBadge code={analysis.category} items={dicts?.categories} />
          <PriorityBadge
            code={analysis.priority}
            items={dicts?.priorities}
            title={analysis.priority_reason}
          />
          <span className="badge">{dictLabel(dicts?.teams, analysis.team)}</span>
          {analysis.service &&
            analysis.service !== dictLabel(dicts?.categories, analysis.category) && (
              <span className="badge">{analysis.service}</span>
            )}
          {percent < 75 && <span className="badge warn">уверенность {percent}%</span>}
        </div>

        {entities.length > 0 && (
          <div className="facts">
            {entities.map(([key, value]) => (
              <span key={key}><b>{ENTITY_LABELS[key] ?? key}</b>{value}</span>
            ))}
          </div>
        )}

        {analysis.missing_fields.length > 0 && (
          <div className="facts warn-facts">
            <span>
              <b>Не хватает</b>
              {analysis.missing_fields.map((f) => f.question).join(' · ')}
            </span>
          </div>
        )}
      </div>

      {analysis.intents.length > 1 && (
        <Section
          title="В обращении несколько вопросов"
          meta={String(analysis.intents.length)}
        >
          <ol className="tight-list">
            {analysis.intents.map((intent, index) => <li key={index}>{intent}</li>)}
          </ol>
        </Section>
      )}
    </>
  )
}
