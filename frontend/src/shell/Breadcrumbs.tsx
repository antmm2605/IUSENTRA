import './shell.css'

export type BreadcrumbItem = {
  label: string
  href?: string
}

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  if (!items.length) return null
  return (
    <nav className="iu-breadcrumbs" aria-label="Percorso">
      {items.map((item, index) => (
        <span key={`${item.label}-${index}`}>
          {item.href ? <a href={item.href}>{item.label}</a> : item.label}
          {index < items.length - 1 ? <span aria-hidden="true">/</span> : null}
        </span>
      ))}
    </nav>
  )
}
