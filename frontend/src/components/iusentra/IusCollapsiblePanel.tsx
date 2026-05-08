import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { cn } from '@/lib/utils'
import type { IusLegalArea, IusTone } from '@/design/iusentraTokens'
import { IusLegalIcon } from './IusLegalIcon'

export function IusCollapsiblePanel({
  title,
  description,
  children,
  defaultOpen = true,
  area,
  icon,
  tone = 'primary',
  className,
}: {
  title: string
  description?: string
  children: ReactNode
  defaultOpen?: boolean
  area?: IusLegalArea
  icon?: LucideIcon
  tone?: IusTone
  className?: string
}) {
  return (
    <Accordion
      type="single"
      collapsible
      defaultValue={defaultOpen ? 'content' : undefined}
      className={cn('ius-collapsible-panel', className)}
    >
      <AccordionItem value="content">
        <AccordionTrigger className="ius-collapsible-panel__trigger">
          <span>
            <IusLegalIcon area={area} icon={icon} tone={tone} />
            <span>
              <strong>{title}</strong>
              {description ? <small>{description}</small> : null}
            </span>
          </span>
        </AccordionTrigger>
        <AccordionContent className="ius-collapsible-panel__content">
          {children}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
