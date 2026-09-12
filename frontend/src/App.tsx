import { useCallback, useEffect, useState } from 'react'
import * as api from './api/client'
import type { Dictionaries, Health } from './types'
import { InboxPage } from './pages/InboxPage'
import { StatsPage } from './pages/StatsPage'
import { TicketsPage } from './pages/TicketsPage'
import { ThemeToggle } from './components/ThemeToggle'

type Tab = 'inbox' | 'tickets' | 'stats'

function LlmChip({ health }: { health: Health | null }) {
  if (!health) return <span className="status-chip">соединяюсь…</span>
  if (health.llm === 'mock') {
    return (
      <span className="status-chip warn" title={health.llm_note ?? ''}>
        <span className="dot warn" />
        Работает на заглушке
      </span>
    )
  }
  if (health.llm === 'error') {
    return (
      <span className="status-chip bad" title={health.llm_note ?? ''}>
        <span className="dot bad" />
        Модель недоступна
      </span>
    )
  }
  return (
    <span className="status-chip">
      <span className="dot ok" />
      {health.model}
    </span>
  )
}

export default function App() {
  const [tab, setTab] = useState<Tab>('inbox')
  const [dicts, setDicts] = useState<Dictionaries>()
  const [health, setHealth] = useState<Health | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [statsKey, setStatsKey] = useState(0)

  const refreshHealth = useCallback(() => {
    void api.getHealth().then(setHealth).catch(() => setHealth(null))
  }, [])

  useEffect(() => {
    void api.getDictionaries().then(setDicts).catch(() => undefined)
    refreshHealth()
  }, [refreshHealth])

  const openMessage = (id: number) => {
    setSelected(id)
    setTab('inbox')
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Salute<span>Agent</span></div>
        <nav className="tabs">
          <button className={`tab ${tab === 'inbox' ? 'active' : ''}`} onClick={() => setTab('inbox')}>
            Инбокс
          </button>
          <button className={`tab ${tab === 'tickets' ? 'active' : ''}`} onClick={() => setTab('tickets')}>
            Заявки
          </button>
          <button className={`tab ${tab === 'stats' ? 'active' : ''}`}
                  onClick={() => { setStatsKey((k) => k + 1); setTab('stats') }}>
            Аналитика
          </button>
        </nav>
        <div className="topbar-right">
          {/* Окно пользователя — отдельная страница: там другой человек
              и другие задачи. Ссылка оставлена для быстрого перехода. */}
          <a className="topbar-link" href="/support" target="_blank" rel="noreferrer">
            Окно пользователя
          </a>
          {health && (
            <span className="status-chip" title={`Фрагментов в индексе: ${health.kb_chunks}`}>
              поиск: {health.retrieval}
            </span>
          )}
          <LlmChip health={health} />
          <ThemeToggle />
        </div>
      </header>

      {tab === 'inbox' && (
        <InboxPage
          dicts={dicts}
          selected={selected}
          onSelect={setSelected}
          onChanged={() => { refreshHealth(); setStatsKey((k) => k + 1) }}
        />
      )}
      {tab === 'tickets' && <TicketsPage dicts={dicts} />}
      {tab === 'stats' && <StatsPage key={statsKey} onOpenMessage={openMessage} />}
    </div>
  )
}
