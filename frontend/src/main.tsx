import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App'
import PortalApp from './PortalApp'

// Два входа в приложение. Рабочее место оператора живёт в корне,
// окно пользователя — по /support. Роутер ради двух страниц не нужен:
// бэкенд отдаёт одну и ту же страницу на любой путь.
const isPortal = window.location.pathname.replace(/\/+$/, '') === '/support'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isPortal ? <PortalApp /> : <App />}
  </StrictMode>,
)
