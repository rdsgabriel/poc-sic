import type { HTMLAttributes } from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-muted text-foreground",
        ok: "border-emerald-300 bg-emerald-100 text-emerald-700",
        pendente: "border-amber-300 bg-amber-100 text-amber-700",
        atencao: "border-orange-300 bg-orange-100 text-orange-700",
        erro: "border-red-300 bg-red-100 text-red-700",
        outline: "text-foreground",
      },
    },
    defaultVariants: { variant: "secondary" },
  }
)

type Props = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>

export function Badge({ className, variant, ...props }: Props) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
