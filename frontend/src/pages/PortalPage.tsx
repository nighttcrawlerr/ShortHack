import { useEffect, useRef, useState } from 'react'
import * as api from '../api/client'
import type { DictItem, PortalReply, PortalStatus } from '../types'

/**
 * Окно пользователя: написать в поддержку и получить ответ.
 *
 * Здесь намеренно нет разбора, трассы и оценок достоверности. Человеку,
 * у которого не работает почта, они не нужны. Он видит то же, что увидел бы
 * в письме от поддержки, и ссылки на инструкции, по которым составлен ответ.
 */

interface Turn {
  role: 'user' | 'assistant'
  text: string
  status?: PortalStatus
  ticketKey?: string | null
  sources?: { title: string; source: string }[]
  seconds?: number
}

const STATUS_NOTE: Record<PortalStatus, { label: string; tone: string }> = {
  answered: { label: 'Ответ по инструкции', tone: 'ok' },
  ticket_created: { label: 'Заявка заведена', tone: 'accent' },
  clarification: { label: 'Нужно уточнение', tone: 'warn' },
  pending_human: { label: 'Передано специалисту', tone: 'warn' },
}

/** Разбивает текст на части, выделяя ссылки вида [1] отдельными значками. */
function renderWithCitations(text: string) {
  // Пробел перед сноской убираем: иначе между словом, значком и точкой
  // появляются две дырки и строка выглядит рваной.
  const parts = text.replace(/ +(\[\d{1,2}\])/g, "$1").split(/(\[\d{1,2}\])/g)
  return parts.map((part, index) => {
    const match = part.match(/^\[(\d{1,2})\]$/)
    if (!match) return <span key={index}>{part}</span>
    return <sup key={index} className="cite">{match[1]}</sup>
  })
}

/** Один заголовок статьи на строку: фрагментов из неё может быть несколько. */
function uniqueSources(sources: { title: string; source: string }[]) {
  const seen = new Set<string>()
  return sources.filter((item) => {
    if (seen.has(item.title)) return false
    seen.add(item.title)
    return true
  })
}

export function PortalPage() {
  const [categories, setCategories] = useState<DictItem[]>([])
  const [greeting, setGreeting] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const [text, setText] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [threadId, setThreadId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    void api.getPortalCategories().then((d) => {
      setCategories(d.categories)
      setGreeting(d.greeting)
    }).catch(() => undefined)
  }, [])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns, busy])

  const send = async () => {
    const value = text.trim()
    if (!value || busy) return

    setTurns((prev) => [...prev, { role: 'user', text: value }])
    setText('')
    setBusy(true)
    setError(null)

    try {
      const reply: PortalReply = await api.portalAsk({
        text: value,
        category: threadId ? null : category,
        message_id: threadId,
      })
      setThreadId(reply.message_id)
      setTurns((prev) => [...prev, {
        role: 'assistant',
        text: reply.reply,
        status: reply.status,
        ticketKey: reply.ticket_key,
        sources: reply.sources,
        seconds: reply.elapsed_ms / 1000,
      }])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const restart = () => {
    setTurns([])
    setThreadId(null)
    setCategory(null)
    setText('')
    setError(null)
  }

  const started = turns.length > 0

  return (
    <div className="portal">
      <div className="portal-inner">
        {!started && (
          <div className="portal-hello">
            <div className="portal-title">Чем помочь?</div>
            <p className="portal-greeting">{greeting}</p>

            <div className="card-title" style={{ marginTop: 22 }}>
              С чем связан вопрос
            </div>
            <div className="chips">
              {categories.map((item) => (
                <button
                  key={item.code}
                  className={`chip ${category === item.code ? 'chosen' : ''}`}
                  onClick={() => setCategory(category === item.code ? null : item.code)}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className="hint" style={{ marginTop: 8 }}>
              Можно не выбирать: мы разберёмся по тексту обращения.
            </div>
          </div>
        )}

        {started && (
          <div className="chat">
            {turns.map((turn, index) => (
              <div key={index} className={`bubble ${turn.role}`}>
                {turn.role === 'assistant' && turn.status && (
                  <div className={`badge ${STATUS_NOTE[turn.status].tone}`}
                       style={{ marginBottom: 8 }}>
                    {STATUS_NOTE[turn.status].label}
                    {turn.ticketKey ? ` · ${turn.ticketKey}` : ''}
                  </div>
                )}
                <div className="bubble-text">
                  {turn.role === 'assistant'
                    ? renderWithCitations(turn.text)
                    : turn.text}
                </div>
                {turn.sources && turn.sources.length > 0 && (
                  <div className="bubble-sources">
                    <div style={{ marginBottom: 2 }}>Ответ составлен по инструкциям:</div>
                    {uniqueSources(turn.sources).map((source, n) => (
                      <div key={n}>— {source.title}</div>
                    ))}
                  </div>
                )}
                {turn.role === 'assistant' && turn.seconds !== undefined && (
                  <div className="bubble-meta">ответ за {turn.seconds.toFixed(1)} с</div>
                )}
              </div>
            ))}

            {busy && (
              <div className="bubble assistant">
                <div className="typing"><span /><span /><span /></div>
              </div>
            )}
            <div ref={bottom} />
          </div>
        )}

        {error && <div className="notice bad">{error}</div>}

        <div className="composer">
          <textarea
            rows={started ? 2 : 5}
            placeholder={started
              ? 'Ответьте на вопросы или уточните детали'
              : 'Опишите, что случилось'}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void send()
            }}
          />
          <div className="composer-row">
            <button className="btn btn-primary" disabled={busy || !text.trim()}
                    onClick={() => void send()}>
              {busy ? 'Отправляю' : 'Отправить'}
            </button>
            {started && (
              <button className="btn btn-ghost" onClick={restart}>Новый вопрос</button>
            )}
            <span className="hint" style={{ marginLeft: 'auto' }}>
              {started ? 'Cmd+Enter' : category
                ? categories.find((c) => c.code === category)?.label
                : 'категория не выбрана'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
