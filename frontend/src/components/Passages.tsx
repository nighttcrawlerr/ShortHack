import type { Passage } from '../types'

export function Passages({ passages, mode }: { passages: Passage[]; mode?: string }) {
  if (!passages.length) return null
  return (
    <div className="card">
      <div className="card-title">
        Источники ответа{mode ? ` · ${mode} поиск` : ''}
      </div>
      {passages.map((passage, index) => (
        <div className="passage" key={passage.chunk_id}>
          <div className="passage-head">
            <span className="passage-no">[{index + 1}]</span>
            <span className="passage-title">{passage.title}</span>
            <span className="badge">{Math.round(passage.score * 100)}%</span>
          </div>
          <div className="passage-text">{passage.text}</div>
          <div className="passage-src">
            {passage.source || 'источник не указан'}
            {passage.matched_terms.length > 0 &&
              ` · совпало: ${passage.matched_terms.slice(0, 6).join(', ')}`}
          </div>
        </div>
      ))}
    </div>
  )
}
