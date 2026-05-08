import { Paperclip } from 'lucide-react'
import { cn } from '@/lib/utils'
import { IusStatusBadge } from './IusStatusBadge'

export type IusMessageListItem = {
  id: string
  sender: string
  recipient?: string
  subject: string
  date: string
  channel?: string
  unread?: boolean
  attachments?: number
  href?: string
}

export function IusMessageList({
  items,
  className,
}: {
  items: IusMessageListItem[]
  className?: string
}) {
  return (
    <div className={cn('ius-message-list', className)} role="list">
      {items.map((item) => {
        const content = (
          <>
            <div>
              <strong>{item.subject || 'Senza oggetto'}</strong>
              <span>{item.sender}{item.recipient ? ` -> ${item.recipient}` : ''}</span>
            </div>
            <div className="ius-message-list__meta">
              {item.channel ? <IusStatusBadge tone="info">{item.channel}</IusStatusBadge> : null}
              {item.unread ? <IusStatusBadge tone="warning">Non letto</IusStatusBadge> : null}
              {item.attachments ? <span><Paperclip aria-hidden="true" /> {item.attachments}</span> : null}
              <time>{item.date}</time>
            </div>
          </>
        )
        return item.href ? (
          <a className="ius-message-list__item" href={item.href} key={item.id} role="listitem">
            {content}
          </a>
        ) : (
          <article className="ius-message-list__item" key={item.id} role="listitem">
            {content}
          </article>
        )
      })}
    </div>
  )
}
