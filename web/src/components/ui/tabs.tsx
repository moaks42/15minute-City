import * as T from '@radix-ui/react-tabs'
import { cn } from '@/lib/utils'
import type { ComponentProps } from 'react'

export const Tabs = T.Root
export const TabsContent = T.Content

export function TabsList({ className, ...p }: ComponentProps<typeof T.List>) {
  return <T.List className={cn('inline-flex rounded-full bg-sunken p-1', className)} {...p} />
}
export function TabsTrigger({ className, ...p }: ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        'min-h-9 rounded-full px-4 text-sm font-medium text-ink-2 transition-colors data-[state=active]:bg-surface data-[state=active]:text-ink data-[state=active]:shadow-sm',
        className,
      )}
      {...p}
    />
  )
}
