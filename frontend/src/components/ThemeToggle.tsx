import { useEffect, useState } from 'react'

type Theme = 'light' | 'dark'

function initial(): Theme {
  try {
    const saved = localStorage.getItem('theme')
    if (saved === 'light' || saved === 'dark') return saved
  } catch { /* приватное окно: хранилище недоступно */ }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initial)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('theme', theme) } catch { /* приватное окно */ }
  }, [theme])

  const next = theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'

  return (
    <button
      className="theme-toggle"
      title={next}
      aria-label={next}
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
