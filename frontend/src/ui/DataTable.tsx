import type { ReactNode } from 'react'
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
  if (!rows.length && empty) return <>{empty}</>
  return (
    <div className="iu-data-table-wrap">
      <table className="iu-data-table">
        <thead>
          <tr>
            {columns.map((column) => <th key={column.key}>{column.header}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={getRowKey(row)}>
              {columns.map((column) => <td key={column.key}>{column.render(row)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
