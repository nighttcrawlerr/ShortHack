/**
 * Знак SaluteAgent: шестиугольник, внутри S и A, собранные одними линиями.
 *
 * Буквы намеренно нарисованы штрихом, а не залиты: на мелком размере заливка
 * слипается в пятно, а линия остаётся читаемой. Толщина штриха букв меньше
 * толщины грани, поэтому шестиугольник читается как рамка, а не как часть букв.
 */
export function Logo({ size = 40, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      role="img"
      aria-label="SaluteAgent"
    >
      {/* Грань шестиугольника */}
      <path
        d="M24 3.2 41.5 13.3v20.2L24 44.8 6.5 33.5V13.3z"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinejoin="round"
      />
      {/* Буквы опущены на 1.2 к оптическому центру шестиугольника: без сдвига
          они висят выше середины, потому что нижняя вершина грани острая. */}
      <g transform="translate(0 1.2)">
      {/* S — одна непрерывная линия */}
      <path
        d="M21.7 18.4c-.6-1.3-2-2-3.6-2-2.1 0-3.7 1.2-3.7 2.9 0 3.6 7.3 2.3 7.3 6.1 0 1.9-1.7 3.2-4 3.2-1.8 0-3.3-.8-3.9-2.2"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* A — две грани и перекладина */}
      <path
        d="M27.2 28.4 31.9 16.4l4.7 12"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M29.1 24.2h5.6"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      </g>
    </svg>
  )
}
