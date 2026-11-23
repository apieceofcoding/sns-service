import type React from "react"
import Link from "next/link"
import { Feather } from "lucide-react"

/** Login and signup share one X-style screen: mark, title, fields, white pill button. */
export function AuthForm({
  title,
  submitLabel,
  pending,
  onSubmit,
  footer,
  children,
}: {
  title: string
  submitLabel: string
  pending: boolean
  onSubmit: () => void
  footer: { text: string; link: string; href: string }
  children: React.ReactNode
}) {
  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          onSubmit()
        }}
        className="flex w-full max-w-[364px] flex-col gap-5"
      >
        <Feather className="size-10" />
        <h1 className="mb-3 text-[31px] font-extrabold leading-9">{title}</h1>
        {children}
        <button
          type="submit"
          disabled={pending}
          className="mt-2 h-[52px] rounded-full bg-secondary text-[17px] font-bold text-secondary-foreground transition-colors hover:bg-secondary/90 disabled:opacity-50"
        >
          {submitLabel}
        </button>
        <p className="text-muted-foreground">
          {footer.text}{" "}
          <Link href={footer.href} className="text-primary hover:underline">
            {footer.link}
          </Link>
        </p>
      </form>
    </main>
  )
}

export function AuthField({
  label,
  ...props
}: { label: string } & React.ComponentProps<"input">) {
  return (
    <label className="group relative block rounded border border-input focus-within:border-primary">
      <span className="absolute left-2 top-2 text-[13px] text-muted-foreground group-focus-within:text-primary">{label}</span>
      <input required {...props} className="h-14 w-full bg-transparent px-2 pt-5 text-[17px] outline-none" />
    </label>
  )
}
