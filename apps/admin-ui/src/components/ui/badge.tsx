import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "purple" | "green" | "red" | "blue"
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-gray-950 focus:ring-offset-2",
        {
          "border-transparent bg-gray-900 text-gray-50 shadow hover:bg-gray-900/80": variant === "default",
          "border-transparent bg-gray-100 text-gray-900 hover:bg-gray-100/80": variant === "secondary",
          "border-transparent bg-red-500 text-gray-50 shadow hover:bg-red-500/80": variant === "destructive",
          "text-gray-950": variant === "outline",
          "border-transparent bg-purple-100 text-purple-800": variant === "purple",
          "border-transparent bg-green-100 text-green-800": variant === "green", 
          "border-transparent bg-blue-100 text-blue-800": variant === "blue",
          "border-transparent bg-red-100 text-red-800": variant === "red",
        },
        className
      )}
      {...props}
    />
  )
}

export { Badge }