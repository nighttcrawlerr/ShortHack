import type { ReactNode } from 'react'

/**
 * Сворачиваемый блок.
 *
 * Оператор смотрит на решение, а не на его обоснование. Трасса агента,
 * источники и разбор проверки нужны ему в двух случаях из десяти, поэтому
 * по умолчанию свёрнуты: в заголовке остаётся только счётчик, чтобы было
 * видно, что там есть содержимое.
 */
export function Section({ title, meta, children, open = false, plain = false }: {
  title: string
  meta?: string
  children: ReactNode
  open?: boolean
  plain?: boolean
}) {
  return (
    <details className={`sec ${plain ? 'sec-plain' : ''}`} open={open}>
      <summary>
        <span className="sec-title">{title}</span>
        {meta && <span className="sec-meta">{meta}</span>}
      </summary>
      <div className="sec-body">{children}</div>
    </details>
  )
}
