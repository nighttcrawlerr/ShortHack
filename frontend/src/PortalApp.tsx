import { PortalPage } from './pages/PortalPage'
import { ThemeToggle } from './components/ThemeToggle'

/**
 * Главная страница продукта: сюда попадает человек, у которого что-то
 * не работает. Про инбокс, заявки и аналитику она ничего не знает —
 * это рабочее место оператора, оно живёт на /admin.
 */
export default function PortalApp() {
  return (
    <div className="app">
      <header className="topbar portal-topbar">
        <div className="brand">Salute<span>Agent</span></div>
        <div className="topbar-title">Служба технической поддержки</div>
        <div className="topbar-right">
          <ThemeToggle />
        </div>
      </header>
      <PortalPage />
    </div>
  )
}
