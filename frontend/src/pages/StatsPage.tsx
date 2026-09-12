import { useEffect, useState } from 'react'
import * as api from '../api/client'
import type { CountItem, Stats } from '../types'

function Chart({ title, items, colors }: {
  title: string; items: CountItem[]; colors?: Record<string, string>
}) {
  if (!items.length) return null
  const max = Math.max(...items.map((i) => i.count))
  return (
    <div className="card">
      <div className="card-title">{title}</div>
      {items.map((item) => (
        <div className="chart-row" key={item.code}>
          <div className="chart-label">{item.label}</div>
          <div className="chart-track">
            <div
              className="chart-fill"
              style={{
                width: `${Math.round((item.count / max) * 100)}%`,
                background: colors?.[item.code] ?? 'var(--accent)',
              }}
            />
          </div>
          <div className="chart-count">{item.count}</div>
        </div>
      ))}
    </div>
  )
}

export function StatsPage({ onOpenMessage }: { onOpenMessage: (id: number) => void }) {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => { void api.getStats().then(setStats) }, [])

  if (!stats) return <div className="empty"><div>Загружаю статистику…</div></div>

  return (
    <div className="page">
      <div className="section-title">Аналитика потока обращений</div>

      <div className="tiles">
        <div className="tile">
          <div className="tile-value">{stats.messages_total}</div>
          <div className="tile-label">обращений в очереди</div>
        </div>
        <div className="tile">
          <div className="tile-value">{stats.messages_analyzed}</div>
          <div className="tile-label">разобрано помощником</div>
        </div>
        <div className="tile">
          <div className="tile-value">{stats.tickets_total}</div>
          <div className="tile-label">заявок завёл агент</div>
        </div>
        <div className="tile">
          <div className="tile-value">{(stats.avg_latency_ms / 1000).toFixed(1)} с</div>
          <div className="tile-label">средний разбор обращения</div>
        </div>
      </div>

      {stats.mass_incidents.length > 0 && (
        <div className="card">
          <div className="card-title">Повторяющиеся проблемы</div>
          {stats.mass_incidents.map((incident, index) => (
            <div key={index} className="notice warn" style={{ marginBottom: 8 }}>
              <div>{incident.hint}</div>
              <div className="btn-row" style={{ marginTop: 8 }}>
                {incident.message_ids.map((id) => (
                  <button key={id} className="btn btn-sm" onClick={() => onOpenMessage(id)}>
                    обращение №{id}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Chart title="По категориям" items={stats.by_category} />
      <Chart
        title="По приоритетам"
        items={stats.by_priority}
        colors={{ P1: 'var(--p1)', P2: 'var(--p2)', P3: 'var(--p3)', P4: 'var(--p4)' }}
      />
      <Chart title="По выбранным действиям" items={stats.by_action} />
    </div>
  )
}
