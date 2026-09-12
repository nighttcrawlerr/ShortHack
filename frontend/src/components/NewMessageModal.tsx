import { useState } from 'react'

const SAMPLE = `Здравствуйте!

Со вчерашнего дня не могу подключиться к корпоративному VPN, клиент выдаёт ошибку ERR_TUNNEL_FAILED. Логин ivanov.ii, Windows 11.

Я на удалённой работе, без VPN не могу работать.`

export function NewMessageModal({ onClose, onCreate, busy }: {
  onClose: () => void
  onCreate: (payload: {
    channel: string; subject: string; author_name: string
    author_email: string; body: string
  }) => void
  busy: boolean
}) {
  const [channel, setChannel] = useState('email')
  const [subject, setSubject] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [body, setBody] = useState('')

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="section-title">Новое обращение</div>
        <div className="notice info">
          Вставьте любой текст письма или расшифровки разговора. Помощник разберёт
          его так же, как остальные обращения.
        </div>

        <div className="field-row">
          <div className="field">
            <label>Канал</label>
            <select value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="email">Письмо</option>
              <option value="call">Звонок</option>
            </select>
          </div>
          <div className="field">
            <label>Тема</label>
            <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)}
                   placeholder="Не обязательно" />
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label>Имя отправителя</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                   placeholder="Иванов Иван" />
          </div>
          <div className="field">
            <label>Почта</label>
            <input type="text" value={email} onChange={(e) => setEmail(e.target.value)}
                   placeholder="ivanov@example.ru" />
          </div>
        </div>

        <div className="field">
          <label>Текст обращения</label>
          <textarea rows={9} value={body} onChange={(e) => setBody(e.target.value)} />
        </div>

        <div className="btn-row">
          <button
            className="btn btn-primary"
            disabled={busy || !body.trim()}
            onClick={() => onCreate({
              channel,
              subject: subject.trim(),
              author_name: name.trim() || 'Неизвестный отправитель',
              author_email: email.trim() || 'unknown@example.ru',
              body,
            })}
          >
            Создать и разобрать
          </button>
          <button className="btn btn-ghost" onClick={() => setBody(SAMPLE)}>
            Вставить пример
          </button>
          <button className="btn btn-ghost" onClick={onClose}>Отмена</button>
        </div>
      </div>
    </div>
  )
}
