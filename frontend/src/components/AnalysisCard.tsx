import type { Analysis, Dictionaries } from '../types'
import { CategoryBadge, PriorityBadge, dictLabel } from './Badge'

const ENTITY_LABELS: Record<string, string> = {
  login: 'Логин',
  full_name: 'ФИО',
  email: 'Почта',
  phone: 'Телефон',
  employee_id: 'Табельный номер',
  service_name: 'Сервис',
  device: 'Устройство',
  os: 'Операционная система',
  browser: 'Браузер',
  error_code: 'Код ошибки',
  occurred_at: 'Когда произошло',
  location: 'Расположение',
  inventory_number: 'Инвентарный номер',
}

export function AnalysisCard({ analysis, dicts }: {
  analysis: Analysis; dicts?: Dictionaries
}) {
  const entities = Object.entries(analysis.entities ?? {})
  const percent = Math.round(analysis.confidence * 100)

  return (
    <>
      {analysis.mass_incident && (
        <div className="notice warn">
          <b>Возможен массовый сбой.</b> За последние часы пришли похожие обращения
          по тому же сервису. Проверьте, не идёт ли общая авария.
        </div>
      )}

      <div className="card">
        <div className="card-title">Суть обращения</div>
        <div className="section-title">{analysis.summary}</div>

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
        </div>

        {analysis.priority_reason && (
          <div className="hint" style={{ marginTop: 8 }}>
            Приоритет: {analysis.priority_reason}
          </div>
        )}

        <div style={{ marginTop: 12 }}>
          <div className="meta" style={{ marginBottom: 4 }}>
            <span>Уверенность разбора</span>
            <span style={{ marginLeft: 'auto' }}>{percent}%</span>
          </div>
          <div className="bar">
            <span
              style={{
                width: `${percent}%`,
                background: percent >= 75 ? 'var(--ok)' : percent >= 50 ? 'var(--warn)' : 'var(--bad)',
              }}
            />
          </div>
        </div>
      </div>

      {analysis.intents.length > 1 && (
        <div className="card">
          <div className="card-title">В обращении несколько вопросов</div>
          <ol style={{ margin: 0, paddingLeft: 20 }}>
            {analysis.intents.map((intent, index) => (
              <li key={index} style={{ marginBottom: 4 }}>{intent}</li>
            ))}
          </ol>
        </div>
      )}

      {entities.length > 0 && (
        <div className="card">
          <div className="card-title">Извлечённые данные</div>
          <dl className="kv">
            {entities.map(([key, value]) => (
              <div key={key} style={{ display: 'contents' }}>
                <dt>{ENTITY_LABELS[key] ?? key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {analysis.missing_fields.length > 0 && (
        <div className="card">
          <div className="card-title">Чего не хватает</div>
          {analysis.missing_fields.map((field, index) => (
            <div key={index} style={{ marginBottom: 9 }}>
              <div style={{ fontWeight: 600 }}>{field.question}</div>
              <div className="claim-note">{field.why}</div>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
