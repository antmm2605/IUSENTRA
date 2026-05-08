import type { ReactNode } from 'react'
import { IusDataTableShell } from '@/components/iusentra'
import './ui.css'

export type DataTableColumn<T> = {
  key: string
  header: string
  render: (row: T) => ReactNode
}

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  empty,
}: {
  columns: DataTableColumn<T>[]
  rows: T[]
  getRowKey: (row: T) => string
  empty?: ReactNode
}) {
  return <IusDataTableShell columns={columns} rows={rows} getRowKey={getRowKey} empty={empty} className="iu-data-table-wrap iu-data-table" />
}
