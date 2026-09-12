import { useEffect, useState } from 'react'
import * as api from '../api/client'
import type { CountItem, Stats } from '../types'
import { Section } from '../components/Section'

/**
 * Горизонтальные полосы от общей нулевой линии.
 *
 * Приоритеты — упорядоченная шкала, а не четыре независимых сущности,
 * поэтому четырьмя цветами их красить нечестно и вдобавок не проходит
 * проверку на дальтонизм: красный и янтарный сливаются. Вместо этого
 * выделен только критический приоритет, остальное — обычный акцент.
 */
function Chart({ title, items, order, critical }: {
  title: string
  items: CountItem[]
  /** Порядковую шкалу нельзя сортировать по величине: P1 обязан быть первым. */
  order?: string[]
  critical?: string
}) {
  if (!items.length) return null
  const rows = order
    ? [...items].sort((a, b) => order.indexOf(a.code) - order.indexOf(b.code))
    : [...items].sort((a, b) => b.count - a.count)
  const max = Math.max(...rows.map((i) => i.count))
  const total = rows.reduce((sum, i) => sum + i.count, 0)

  return (
    <div className="card">
      <div className="card-title">{title}</div>
      <div className="chart">
        {rows.map((item) => {
          const share = total ? Math.round((item.count / total) * 100) : 0
          return (
            <div className="crow" key={item.code} title={`${item.label}: ${item.count} из ${total} (${share}%)`}>
              <div className="clabel">{item.label}</div>
              <div className="ctrack">
                <div
                  className={`cfill ${critical && item.code === critical ? 'crit' : ''}`}
                  style={{ width: `${max ? (item.count / max) * 100 : 0}%` }}
                />
              </div>
              <div className="cval">
                {item.count}
                <span className="cshare">{share}%</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function StatsPage({ onOpenMessage }: { onOpenMessage: (id: number) => void }) {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => { void api.getStats().then(setStats) }, [])

  if (!stats) return <div className="empty"><div>Загружаю статистику…</div></div>

  return (
    <div className="page">
      <div className="tiles">
        <div className="tile">
          <div className="tile-value">{stats.messages_analyzed}</div>
          <div className="tile-label">обращений разобрано из {stats.messages_total}</div>
        </div>
        <div className="tile">
          <div className="tile-value">{Math.round(stats.auto_actionable_share * 100)}%</div>
          <div className="tile-label">разобрано уверенно</div>
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

      {stats.mass_incidents.map((incident, index) => (
        <div key={index} className="notice warn">
          <b>Возможен массовый сбой.</b> {incident.hint}
          <div className="btn-row" style={{ marginTop: 10 }}>
            {incident.message_ids.map((id) => (
              <button key={id} className="btn btn-sm" onClick={() => onOpenMessage(id)}>
                обращение №{id}
              </button>
            ))}
          </div>
        </div>
      ))}

      <Chart
        title="По приоритетам"
        items={stats.by_priority}
        order={['P1', 'P2', 'P3', 'P4']}
        critical="P1"
      />
      <Chart title="По категориям" items={stats.by_category} />

      <Section title="По выбранным действиям" meta={String(stats.by_action.length)}>
        <div className="chart">
          {[...stats.by_action].sort((a, b) => b.count - a.count).map((item) => {
            const max = Math.max(...stats.by_action.map((i) => i.count))
            return (
              <div className="crow" key={item.code}>
                <div className="clabel">{item.label}</div>
                <div className="ctrack">
                  <div className="cfill" style={{ width: `${max ? (item.count / max) * 100 : 0}%` }} />
                </div>
                <div className="cval">{item.count}</div>
              </div>
            )
          })}
        </div>
      </Section>
    </div>
  )
}
