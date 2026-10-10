import type { ButtonHTMLAttributes, PointerEvent, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent'
type Size = 'sm' | 'md' | 'lg'

interface BaseProps {
  variant?: Variant
  size?: Size
  icon?: ReactNode
  iconRight?: ReactNode
  block?: boolean
}

function cls(variant: Variant, size: Size, block?: boolean, extra?: string) {
  return ['btn', `btn--${variant}`, size !== 'md' && `btn--${size}`, block && 'btn--block', extra]
    .filter(Boolean)
    .join(' ')
}

/** Подсветка, следующая за курсором: координаты передаются в CSS-переменные. */
function trackGlow(e: PointerEvent<HTMLElement>) {
  const el = e.currentTarget
  const r = el.getBoundingClientRect()
  el.style.setProperty('--mx', `${e.clientX - r.left}px`)
  el.style.setProperty('--my', `${e.clientY - r.top}px`)
}

type ButtonProps = BaseProps & ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }

export function Button({
  variant = 'primary',
  size = 'md',
  icon,
  iconRight,
  block,
  loading,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cls(variant, size, block, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      onPointerMove={trackGlow}
      {...rest}
    >
      {loading ? <Loader2 size={16} className="spin" aria-hidden /> : icon}
      {children && <span>{children}</span>}
      {iconRight}
    </button>
  )
}

type LinkButtonProps = BaseProps & LinkProps

export function LinkButton({ variant = 'primary', size = 'md', icon, iconRight, block, className, children, ...rest }: LinkButtonProps) {
  return (
    <Link className={cls(variant, size, block, className)} onPointerMove={trackGlow} {...rest}>
      {icon}
      {children && <span>{children as ReactNode}</span>}
      {iconRight}
    </Link>
  )
}
