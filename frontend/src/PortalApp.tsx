import { PortalPage } from './pages/PortalPage'
import { ThemeToggle } from './components/ThemeToggle'

/**
 * Отдельная страница для того, кто обращается в поддержку.
 *
 * Живёт по адресу /support и намеренно ничего не знает про инбокс, заявки
 * и аналитику: это интерфейс для человека с проблемой, а не для оператора.
 * Общими остаются только палитра и тема.
 */
export default function PortalApp() {
  return (
    <div className="app">
      <header className="topbar">
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
