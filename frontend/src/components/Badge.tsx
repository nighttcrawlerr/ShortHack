import type { DictItem } from '../types'

const label = (items: DictItem[] | undefined, code: string | null) =>
  items?.find((i) => i.code === code)?.label ?? code ?? ''

export function Badge({ text, tone }: { text: string; tone?: string }) {
  return <span className={`badge ${tone ?? ''}`}>{text}</span>
}

export function PriorityBadge({ code, items, title }: {
  code: string | null; items?: DictItem[]; title?: string
}) {
  if (!code) return null
  return (
    <span className={`badge ${code.toLowerCase()}`} title={title}>
      {code} · {label(items, code)}
    </span>
  )
}

export function CategoryBadge({ code, items }: { code: string | null; items?: DictItem[] }) {
  if (!code) return null
  return <span className="badge">{label(items, code)}</span>
}

export function ChannelBadge({ code }: { code: string }) {
  const isCall = code === 'call'
  return <span className="badge">{isCall ? '☎ Звонок' : '✉ Письмо'}</span>
}

export function StatusBadge({ code, items }: { code: string; items?: DictItem[] }) {
  const tone = code === 'proposed' ? 'accent'
    : code === 'open' ? 'p3'
    : code === 'closed' ? 'ok'
    : code === 'rejected' ? 'bad'
    : code === 'waiting_user' ? 'warn'
    : code === 'processed' ? 'ok'
    : ''
  return <span className={`badge ${tone}`}>{label(items, code)}</span>
}

export { label as dictLabel }
