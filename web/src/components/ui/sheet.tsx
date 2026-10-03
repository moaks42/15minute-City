import * as D from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

/** Side drawer on desktop, bottom sheet on mobile. */
export function Sheet({
  open,
  onOpenChange,
  title,
  children,
  side = 'right',
  className,
  modal = true,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  title: ReactNode
  children: ReactNode
  side?: 'right' | 'left' | 'bottom'
  className?: string
  modal?: boolean
}) {
  const { t } = useTranslation()
  const pos = {
    right: 'right-0 top-0 h-full w-full sm:w-[460px] border-l data-[state=open]:animate-[slideInR_.2s_ease-out]',
    left: 'left-0 top-0 h-full w-full sm:w-[420px] border-r data-[state=open]:animate-[slideInL_.2s_ease-out]',
    bottom: 'bottom-0 left-0 right-0 max-h-[88dvh] rounded-t-2xl border-t data-[state=open]:animate-[slideInB_.2s_ease-out]',
  }[side]
  return (
    <D.Root open={open} onOpenChange={onOpenChange} modal={modal}>
      <D.Portal>
        {modal && <D.Overlay className="fixed inset-0 z-40 bg-ink/25" />}
        <D.Content
          onInteractOutside={modal ? undefined : (e) => e.preventDefault()}
          className={cn('fixed z-50 flex flex-col border-line bg-surface shadow-[var(--shadow-pop)] outline-none', pos, className)}
        >
          <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
            <D.Title className="font-display text-xl font-semibold leading-tight">{title}</D.Title>
            <D.Close className="-mr-2 grid h-11 w-11 shrink-0 place-items-center rounded-full text-ink-2 hover:bg-sunken" aria-label={t('nav.close')}>
              <X size={20} />
            </D.Close>
          </div>
          <D.Description className="sr-only">{title}</D.Description>
          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        </D.Content>
      </D.Portal>
    </D.Root>
  )
}
