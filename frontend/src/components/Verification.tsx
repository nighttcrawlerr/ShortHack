import type { Verification } from '../types'
import { Section } from './Section'

const STATUS: Record<string, { label: string; tone: string }> = {
  verified: { label: 'Проверено', tone: 'ok' },
  needs_review: { label: 'Нужен взгляд человека', tone: 'warn' },
  rejected: { label: 'Отклонено проверкой', tone: 'bad' },
  insufficient: { label: 'Отвечать нечем', tone: 'warn' },
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
  questions: 'Из них вопросов к пользователю',
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
      <div className="verdict">
        <span className={`dot ${meta.tone}`} />
        <b>{meta.label}</b>
        <span className="verdict-score">{percent}%</span>
      </div>

      <div className="bar" style={{ marginTop: 9 }}>
        <span
          style={{
            width: `${percent}%`,
            background: percent >= 85 ? 'var(--ok)' : percent >= 60 ? 'var(--warn)' : 'var(--bad)',
          }}
        />
      </div>


      <Section
        plain
        title={verification.issues.length
          ? `Замечаний: ${verification.issues.length}`
          : 'Проверка по пунктам'}
        meta={`${verification.latency_ms} мс · ${verification.model_used ? 'с моделью' : 'только код'}`}
      >
        <dl className="kv">
          {Object.entries(verification.checks).map(([key, value]) => (
            <div key={key} style={{ display: 'contents' }}>
              <dt>{CHECK_LABELS[key] ?? key}</dt>
              <dd>{formatCheck(key, value)}</dd>
            </div>
          ))}
        </dl>

        {verification.issues.length > 0 && (
          <div style={{ marginTop: 12 }}>
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
          </div>
        )}

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
      </Section>
    </div>
  )
}
