/**
 * Знак SaluteAgent.
 *
 * Шестиугольник, внутри — непрерывная ломаная, сложенная из двух движений:
 * спуск и подъём образуют вершину, как у «А», а верхний виток уходит влево
 * и возвращается, как у «S». Буквы не написаны, а собраны: узнаются
 * не с первого взгляда, и это намеренно — знак должен работать как форма,
 * а не читаться по складам.
 *
 * Второй смысл формы: линия идёт вниз, разворачивается и уходит вверх.
 * Это обращение, которое пришло, было разобрано и вернулось ответом.
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
      {/* Грань. Толще внутренней линии, поэтому читается как рамка. */}
      <path
        d="M24 3.4 41.3 13.4v20.2L24 43.6 6.7 33.6V13.4z"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />

      {/* Ломаная: виток слева, спуск, вершина, подъём */}
      <path
        d="M30.4 16.3c-1.6-2-4.4-2.4-6.4-1.1-2.2 1.4-2.5 4.3-.8 6.1l-6.6 11.1"
        stroke="currentColor"
        strokeWidth="2.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M23.2 21.3 31.4 32.4"
        stroke="currentColor"
        strokeWidth="2.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Перекладина замыкает вершину. Приглушать её нельзя: на мелком
          размере полупрозрачная линия исчезает первой, и знак разваливается
          на две несвязанные черты. */}
      <path
        d="M20.6 28h7.2"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  )
}
