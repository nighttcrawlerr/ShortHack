import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import App from './App'
import PortalApp from './PortalApp'

// Два входа в приложение. Главная страница — чат с пользователем: его видят
// все, кто обращается в поддержку. Рабочее место оператора живёт на /admin.
// Роутер ради двух страниц не нужен: бэкенд отдаёт одну и ту же страницу
// на любой путь.
const path = window.location.pathname.replace(/\/+$/, '')
const isOperator = path === '/admin'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isOperator ? <App /> : <PortalApp />}
  </StrictMode>,
)
