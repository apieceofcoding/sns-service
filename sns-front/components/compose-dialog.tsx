"use client"

import { useState } from "react"
import { X } from "lucide-react"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { useAuth } from "@/hooks/api/use-auth"
import { UserAvatar } from "./user-avatar"

/** X-style write dialog used for replies and quotes. */
export function ComposeDialog({
  open,
  onOpenChange,
  title,
  placeholder,
  submitLabel,
  pending,
  onSubmit,
  above,
  below,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  placeholder: string
  submitLabel: string
  pending: boolean
  onSubmit: (content: string, done: () => void) => void
  above?: React.ReactNode
  below?: React.ReactNode
}) {
  const { user } = useAuth()
  const [content, setContent] = useState("")

  const close = () => {
    setContent("")
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
      <DialogContent
        showCloseButton={false}
        onClick={(e) => e.stopPropagation()}
        className="top-[5%] max-w-[600px] translate-y-0 gap-0 rounded-2xl border-none p-0 sm:max-w-[600px]"
      >
        <DialogTitle className="sr-only">{title}</DialogTitle>
        <div className="flex h-[53px] items-center px-2">
          <button type="button" aria-label="닫기" onClick={close} className="flex size-9 items-center justify-center rounded-full hover:bg-foreground/10">
            <X className="size-5" />
          </button>
        </div>
        {above}
        <div className="flex gap-3 px-4">
          <UserAvatar username={user?.username} imageUrl={user?.profileImageUrl} />
          <div className="min-w-0 flex-1">
            <textarea
              autoFocus
              rows={3}
              placeholder={placeholder}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full resize-none bg-transparent py-2 text-xl outline-none placeholder:text-muted-foreground"
            />
            {below}
          </div>
        </div>
        <div className="mx-4 mt-3 flex justify-end border-t border-border py-3">
          <button
            type="button"
            disabled={!content.trim() || pending}
            onClick={() => onSubmit(content.trim(), close)}
            className="h-9 rounded-full bg-secondary px-4 font-bold text-secondary-foreground hover:bg-secondary/90 disabled:opacity-50"
          >
            {submitLabel}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
