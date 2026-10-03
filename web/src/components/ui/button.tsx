import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const button = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none min-h-11',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-accent-ink hover:bg-accent-strong shadow-sm',
        secondary: 'bg-surface text-ink border border-line hover:border-line-strong hover:bg-sunken',
        ghost: 'text-ink-2 hover:bg-sunken hover:text-ink',
        link: 'text-accent underline-offset-4 hover:underline min-h-0 px-0',
      },
      size: {
        sm: 'h-9 min-h-9 px-3 text-sm',
        md: 'h-11 px-5 text-[15px]',
        lg: 'h-13 px-7 text-base',
        icon: 'h-11 w-11',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> {
  asChild?: boolean
}

export function Button({ className, variant, size, asChild, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : 'button'
  return <Comp className={cn(button({ variant, size }), className)} {...props} />
}
