import * as React from "react"
import * as ToastPrimitive from "@radix-ui/react-toast"
import { X } from "lucide-react"
import { cn } from "../../lib/utils"
import { useToast } from "../../hooks/use-toast"

const ToastProvider = ToastPrimitive.Provider
const ToastViewport = React.forwardRef(({ className, ...props }, ref) => (
  <ToastPrimitive.Viewport ref={ref} className={cn("fixed top-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[420px]", className)} {...props} />
))
ToastViewport.displayName = ToastPrimitive.Viewport.displayName

const Toast = React.forwardRef(({ className, variant, ...props }, ref) => (
  <ToastPrimitive.Root ref={ref} className={cn("group pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-md border p-6 pr-8 shadow-lg transition-all", className)} {...props} />
))
Toast.displayName = ToastPrimitive.Root.displayName

const ToastAction = React.forwardRef(({ className, ...props }, ref) => (
  <ToastPrimitive.Action ref={ref} className={cn("inline-flex h-8 shrink-0 items-center justify-center rounded-md border bg-transparent px-3 text-sm font-medium", className)} {...props} />
))
ToastAction.displayName = ToastPrimitive.Action.displayName

const ToastClose = React.forwardRef(({ className, ...props }, ref) => (
  <ToastPrimitive.Close ref={ref} className={cn("absolute right-2 top-2 rounded-md p-1 opacity-0 transition-opacity group-hover:opacity-100", className)} toast-close="" {...props}>
    <X className="h-4 w-4" />
  </ToastPrimitive.Close>
))
ToastClose.displayName = ToastPrimitive.Close.displayName

const ToastTitle = React.forwardRef(({ className, ...props }, ref) => (
  <ToastPrimitive.Title ref={ref} className={cn("text-sm font-semibold", className)} {...props} />
))
ToastTitle.displayName = ToastPrimitive.Title.displayName

const ToastDescription = React.forwardRef(({ className, ...props }, ref) => (
  <ToastPrimitive.Description ref={ref} className={cn("text-sm opacity-90", className)} {...props} />
))
ToastDescription.displayName = ToastPrimitive.Description.displayName

// Güvenlik ağı: title/description'a yanlışlıkla ham obje/dizi verilirse (örn.
// FastAPI 422 detail dizisi [{type,loc,msg,input,url}]) React #31 ile çökmeyi
// önle — her değeri okunur bir string'e indir.
function guvenliMetin(deger) {
  if (deger == null || typeof deger === "string") return deger
  if (React.isValidElement(deger)) return deger
  if (Array.isArray(deger)) return deger.map(guvenliMetin).filter(Boolean).join("; ")
  if (typeof deger === "object") {
    if (typeof deger.msg === "string") {
      const yer = Array.isArray(deger.loc) ? deger.loc.filter((x) => x !== "body").join(".") : ""
      return yer ? `${yer}: ${deger.msg}` : deger.msg
    }
    try { return JSON.stringify(deger) } catch { return String(deger) }
  }
  return String(deger)
}

function Toaster() {
  const { toasts } = useToast()
  return (
    <ToastProvider>
      {toasts.map(function ({ id, title, description, action, ...props }) {
        const t = guvenliMetin(title)
        const d = guvenliMetin(description)
        return (
          <Toast key={id} {...props}>
            <div className="grid gap-1">
              {t && <ToastTitle>{t}</ToastTitle>}
              {d && <ToastDescription>{d}</ToastDescription>}
            </div>
            {action}
            <ToastClose />
          </Toast>
        )
      })}
      <ToastViewport />
    </ToastProvider>
  )
}

export { Toaster, Toast, ToastAction, ToastClose, ToastTitle, ToastDescription, ToastViewport }
