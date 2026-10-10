import type { CSSProperties, ElementType, ReactNode } from 'react'
import { useInView } from '../../hooks/useReveal'

interface Props {
  children: ReactNode
  delay?: number
  as?: ElementType
  className?: string
}

/** Плавное появление блока при прокрутке. */
export default function Reveal({ children, delay = 0, as: Tag = 'div', className = '' }: Props) {
  const { ref, inView } = useInView<HTMLElement>()
  return (
    <Tag ref={ref} className={`reveal ${inView ? 'is-in' : ''} ${className}`} style={{ '--d': `${delay}ms` } as CSSProperties}>
      {children}
    </Tag>
  )
}
