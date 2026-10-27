import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
  {
    variants: {
      variant: {
        // Primary action. On the recapture screen this is "Take again".
        primary: "bg-text text-bg hover:opacity-90 ring-text",
        // Quieter action that must not compete with the primary one.
        secondary:
          "bg-surface text-text border border-border-subtle hover:bg-border-subtle/40 ring-text",
        danger: "bg-reject text-bg hover:opacity-90 ring-reject",
        ghost: "bg-transparent text-text hover:bg-surface ring-text",
      },
      size: {
        // 44px minimum touch target: camp operators work fast, often on tablets.
        md: "h-11 px-4 text-body",
        lg: "h-14 px-6 text-subhead",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
)
Button.displayName = "Button"

export { Button, buttonVariants }
