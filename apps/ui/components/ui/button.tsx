import * as React from "react"
import { cn } from "@/lib/utils"

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  asChild?: boolean
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link"
  size?: "default" | "sm" | "lg" | "icon"
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", asChild = false, children, ...props }, ref) => {
    const buttonClasses = cn(
      "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-400 disabled:pointer-events-none disabled:opacity-50",
      {
        "bg-blue-600 text-white shadow hover:bg-blue-700": variant === "default",
        "bg-red-600 text-white shadow-sm hover:bg-red-700": variant === "destructive",
        "border border-white/10 bg-transparent shadow-sm hover:bg-white/5 text-slate-300 hover:text-white": variant === "outline",
        "bg-slate-800 text-slate-300 shadow-sm hover:bg-slate-700 hover:text-white": variant === "secondary",
        "hover:bg-white/5 text-slate-300 hover:text-white": variant === "ghost",
        "text-blue-400 underline-offset-4 hover:underline hover:text-blue-300": variant === "link",
      },
      {
        "h-9 px-4 py-2": size === "default",
        "h-8 rounded-md px-3 text-xs": size === "sm",
        "h-10 rounded-md px-8": size === "lg",
        "h-9 w-9": size === "icon",
      },
      className
    )

    if (asChild) {
      // When asChild is true, apply the styles to the child element
      return React.isValidElement(children)
        ? React.cloneElement(children, {
            className: cn(buttonClasses, children.props.className),
            ref,
            ...props,
          } as any)
        : null
    }

    return (
      <button
        className={buttonClasses}
        ref={ref}
        {...props}
      >
        {children}
      </button>
    )
  }
)
Button.displayName = "Button"

export { Button }