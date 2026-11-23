import type React from "react"
import { Sidebar } from "./sidebar"

/** Left navigation and a 600px center column, as on X. */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen justify-center">
      <Sidebar />
      <main className="min-h-screen w-full max-w-[600px] border-x border-border">{children}</main>
      <div className="hidden w-[350px] shrink-0 lg:block" />
    </div>
  )
}

/** Sticky page title with a back button. */
export function PageHeader({ title, subtitle, onBack }: { title: string; subtitle?: string; onBack: () => void }) {
  return (
    <div className="sticky top-0 z-10 flex h-[53px] items-center gap-6 bg-background/65 px-4 backdrop-blur-md">
      <button
        type="button"
        aria-label="뒤로"
        onClick={onBack}
        className="-ml-2 flex size-9 items-center justify-center rounded-full transition-colors hover:bg-foreground/10"
      >
        <svg viewBox="0 0 24 24" className="size-5 fill-current" aria-hidden>
          <path d="M7.414 13l5.043 5.04-1.414 1.42L3.586 12l7.457-7.46 1.414 1.42L7.414 11H21v2H7.414z" />
        </svg>
      </button>
      <div className="min-w-0">
        <h1 className="truncate text-xl font-bold leading-6">{title}</h1>
        {subtitle && <p className="text-[13px] text-muted-foreground">{subtitle}</p>}
      </div>
    </div>
  )
}
