import type { ReactNode } from 'react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'
import { IusEmptyState } from './IusEmptyState'

export type IusDataTableColumn<T> = {
  key: string
  header: string
  render: (row: T) => ReactNode
}

export function IusDataTableShell<T>({
  columns,
  rows,
  getRowKey,
  empty,
  className,
  ariaLabel = 'Tabella dati operativi',
}: {
  columns: IusDataTableColumn<T>[]
  rows: T[]
  getRowKey: (row: T) => string
  empty?: ReactNode
  className?: string
  ariaLabel?: string
}) {
  if (!rows.length) {
    return empty ? <>{empty}</> : <IusEmptyState title="Nessun dato disponibile" message="Quando saranno presenti dati reali compariranno in questa tabella." />
  }

  return (
    <div className={cn('ius-data-table-shell', className)}>
      <Table aria-label={ariaLabel}>
        <TableHeader>
          <TableRow>
            {columns.map((column) => <TableHead key={column.key}>{column.header}</TableHead>)}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={getRowKey(row)}>
              {columns.map((column) => <TableCell key={column.key} data-label={column.header}>{column.render(row)}</TableCell>)}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
