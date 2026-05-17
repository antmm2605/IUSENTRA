import type { ButtonHTMLAttributes, ReactNode } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: ReactNode
  size?: ButtonSize
  variant?: ButtonVariant
}

const joinClassNames = (...values: Array<string | false | null | undefined>) =>
  values.filter(Boolean).join(' ')

export function Button({
  children,
  className,
  icon,
  size = 'md',
  type = 'button',
  variant = 'primary',
  ...props
}: ButtonProps) {
  return (
    <button
      className={joinClassNames(
        'iusentra-button',
        `iusentra-button--${variant}`,
        `iusentra-button--${size}`,
        className,
      )}
      type={type}
      {...props}
    >
      {icon}
      {children}
    </button>
  )
}
