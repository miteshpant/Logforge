import * as React from "react"
import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

const Select = ({ children, value, onValueChange }: {
  children: React.ReactNode
  value?: string
  onValueChange?: (value: string) => void
}) => {
  const [isOpen, setIsOpen] = React.useState(false)
  const [selectedValue, setSelectedValue] = React.useState(value || "")

  const handleSelect = (newValue: string) => {
    setSelectedValue(newValue)
    onValueChange?.(newValue)
    setIsOpen(false)
  }

  return (
    <div className="relative">
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as any, {
            isOpen,
            setIsOpen,
            selectedValue,
            handleSelect,
          })
        }
        return child
      })}
    </div>
  )
}

const SelectTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    isOpen?: boolean
    setIsOpen?: (open: boolean) => void
    selectedValue?: string
  }
>(({ className, children, isOpen, setIsOpen, selectedValue, ...props }, ref) => (
  <button
    ref={ref}
    className={cn(
      "flex h-9 w-full items-center justify-between whitespace-nowrap rounded-md border border-white/10 bg-slate-800/50 px-3 py-2 text-sm text-white shadow-sm ring-offset-slate-900 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50",
      className
    )}
    onClick={() => setIsOpen?.(!isOpen)}
    {...props}
  >
    {children}
    <ChevronDown className="h-4 w-4 opacity-50" />
  </button>
))
SelectTrigger.displayName = "SelectTrigger"

const SelectValue = ({ placeholder, selectedValue }: {
  placeholder?: string
  selectedValue?: string
}) => (
  <span>{selectedValue || placeholder}</span>
)

const SelectContent = ({ children, isOpen, handleSelect }: {
  children: React.ReactNode
  isOpen?: boolean
  handleSelect?: (value: string) => void
}) => {
  if (!isOpen) return null

  return (
    <div className="absolute top-full left-0 z-50 w-full min-w-[8rem] overflow-hidden rounded-md border border-white/10 bg-slate-800 text-white shadow-md">
      <div className="p-1">
        {React.Children.map(children, (child) => {
          if (React.isValidElement(child)) {
            return React.cloneElement(child as any, { handleSelect })
          }
          return child
        })}
      </div>
    </div>
  )
}

const SelectItem = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    value: string
    handleSelect?: (value: string) => void
  }
>(({ className, children, value, handleSelect, ...props }, ref) => {
  // Extract handleSelect from props to prevent it from being passed to DOM
  const { handleSelect: _, ...domProps } = props as any
  
  return (
    <div
      ref={ref}
      className={cn(
        "relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-2 pr-8 text-sm outline-none hover:bg-white/10 focus:bg-white/10",
        className
      )}
      onClick={() => handleSelect?.(value)}
      {...domProps}
    >
      {children}
    </div>
  )
})
SelectItem.displayName = "SelectItem"

export { Select, SelectContent, SelectItem, SelectTrigger, SelectValue }