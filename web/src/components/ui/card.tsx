import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export function Card({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-[var(--radius-card)] border border-line bg-surface shadow-[var(--shadow-card)]', className)} {...p} />
}

export function Badge({ className, ...p }: HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn('inline-flex items-center gap-1 rounded-full bg-sunken px-2 py-0.5 text-xs font-medium text-ink-2', className)} {...p} />
}
