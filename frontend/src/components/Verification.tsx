import type { Verification } from '../types'

const STATUS: Record<string, { label: string; tone: string; note: string }> = {
  verified: {
    label: 'Проверено',
    tone: 'ok',
    note: 'Каждое утверждение опирается на источник. Ответ можно отправлять.',
  },
  needs_review: {
    label: 'Нужен взгляд человека',
    tone: 'warn',
    note: 'Часть утверждений подтверждена не полностью. Прочитайте перед отправкой.',
  },
  rejected: {
    label: 'Отклонено проверкой',
    tone: 'bad',
    note: 'В ответе нашлись утверждения без опоры на источники. Ответ не отправляется.',
  },
  insufficient: {
    label: 'Отвечать нечем',
    tone: 'warn',
    note: 'В базе знаний нет подходящего материала. Помощник не стал сочинять ответ.',
  },
}

const CHECK_LABELS: Record<string, string> = {
  citations_valid: 'Все ссылки разрешаются',
  cited_share: 'Доля утверждений со ссылкой',
  facts_grounded: 'Числа и контакты из источников',
  lexical_coverage: 'Совпадение слов с источниками',
  no_unsupported_promises: 'Нет обещаний сроков и гарантий',
  model_supported_share: 'Подтверждено проверяющей моделью',
  model_claims: 'Проверено утверждений',
  sentences: 'Утверждений в ответе',
  sources: 'Передано фрагментов',
}

const VERDICT_MARK: Record<string, string> = {
  supported: '✓',
  not_found: '?',
  contradicted: '✕',
}

const VERDICT_TEXT: Record<string, string> = {
  supported: 'подтверждено',
  not_found: 'не найдено в источниках',
  contradicted: 'противоречит источнику',
}

function formatCheck(key: string, value: unknown): string {
  if (typeof value === 'boolean') return value ? 'да' : 'нет'
  if (typeof value === 'number') {
    return key.includes('share') || key.includes('coverage')
      ? `${Math.round(value * 100)}%`
      : String(value)
  }
  return String(value)
}

export function VerificationPanel({ verification }: { verification: Verification }) {
  const meta = STATUS[verification.status] ?? STATUS.needs_review
  const percent = Math.round(verification.score * 100)

  return (
    <div className="card">
      <div className="card-title">Проверка на искажения</div>

      <div className={`notice ${meta.tone}`} style={{ marginBottom: 12 }}>
        <b>{meta.label} · {percent}%</b>
        <div style={{ marginTop: 3 }}>{meta.note}</div>
      </div>

      <div className="bar" style={{ marginBottom: 12 }}>
        <span
          style={{
            width: `${percent}%`,
            background: percent >= 85 ? 'var(--ok)' : percent >= 60 ? 'var(--warn)' : 'var(--bad)',
          }}
        />
      </div>

      <dl className="kv" style={{ marginBottom: verification.issues.length ? 12 : 0 }}>
        {Object.entries(verification.checks).map(([key, value]) => (
          <div key={key} style={{ display: 'contents' }}>
            <dt>{CHECK_LABELS[key] ?? key}</dt>
            <dd>{formatCheck(key, value)}</dd>
          </div>
        ))}
      </dl>

      {verification.issues.length > 0 && (
        <>
          <div className="card-title">Что не сошлось</div>
          {verification.issues.map((issue, index) => (
            <div key={index} className={`issue ${issue.severity}`}>
              <div>
                <div>{issue.explanation}</div>
                {issue.fragment && (
                  <div className="claim-note">фрагмент: «{issue.fragment}»</div>
                )}
              </div>
            </div>
          ))}
        </>
      )}

      {verification.claims.length > 0 && (
        <>
          <div className="card-title" style={{ marginTop: 12 }}>
            Разбор по утверждениям
          </div>
          {verification.claims.map((claim, index) => (
            <div key={index} className={`claim ${claim.verdict}`}>
              <div className="claim-mark">{VERDICT_MARK[claim.verdict]}</div>
              <div>
                <div className="claim-text">{claim.text}</div>
                <div className="claim-note">
                  {VERDICT_TEXT[claim.verdict]}
                  {claim.source ? ` · источник [${claim.source}]` : ''}
                  {claim.comment ? ` · ${claim.comment}` : ''}
                </div>
              </div>
            </div>
          ))}
        </>
      )}

      <div className="hint" style={{ marginTop: 10 }}>
        Проверка заняла {verification.latency_ms} мс
        {verification.model_used
          ? ', включая отдельный вызов проверяющей модели'
          : ', только программные правила без обращения к модели'}
      </div>
    </div>
  )
}
