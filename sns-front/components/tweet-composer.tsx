"use client"

import { useEffect, useRef, useState } from "react"
import { ImageIcon, Loader2, X } from "lucide-react"
import { useCreatePost } from "@/hooks/api/use-posts"
import { useMediaUpload } from "@/hooks/api/use-media"
import { useAuth } from "@/hooks/api/use-auth"
import { cn } from "@/lib/utils"
import { UserAvatar } from "./user-avatar"

const MAX_MEDIA = 4

export function TweetComposer() {
  const [content, setContent] = useState("")
  const { user } = useAuth()
  const createPost = useCreatePost()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { uploadingMedia, completedMediaIds, uploadMedia, removeMedia, clearAll, isUploading } = useMediaUpload()

  // The sidebar's 게시하기 opens home with ?compose from other pages.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("compose")) document.getElementById("composer")?.focus()
  }, [])

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).slice(0, MAX_MEDIA - uploadingMedia.length)
    for (const file of files) {
      if (file.type.startsWith("image/") || file.type.startsWith("video/")) await uploadMedia(file)
    }
    e.target.value = ""
  }

  const canSubmit = (content.trim() || completedMediaIds.length > 0) && !isUploading && !createPost.isPending

  const handleSubmit = () => {
    if (!canSubmit) return
    createPost.mutate(
      { content: content.trim(), mediaIds: completedMediaIds },
      {
        onSuccess: () => {
          setContent("")
          clearAll()
        },
      },
    )
  }

  return (
    <div className="flex gap-3 border-b border-border px-4 pt-3">
      <UserAvatar username={user?.username} imageUrl={user?.profileImageUrl} />
      <div className="min-w-0 flex-1">
        <textarea
          id="composer"
          rows={2}
          placeholder="무슨 일이 일어나고 있나요?"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="w-full resize-none bg-transparent py-2 text-xl outline-none placeholder:text-muted-foreground"
        />

        {uploadingMedia.length > 0 && (
          <div className={cn("mb-3 grid gap-2", uploadingMedia.length > 1 && "grid-cols-2")}>
            {uploadingMedia.map((media) => (
              <div key={media.id} className="relative aspect-video overflow-hidden rounded-2xl bg-muted">
                {media.file.type.startsWith("video/") ? (
                  <video src={media.preview} className="size-full object-cover" muted loop autoPlay playsInline />
                ) : (
                  <img src={media.preview} alt="" className="size-full object-cover" />
                )}
                {media.status === "uploading" && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/50 text-sm">
                    <Loader2 className="mr-2 size-5 animate-spin" />
                    {media.progress}%
                  </div>
                )}
                {media.status === "error" && (
                  <div className="absolute inset-0 flex items-center justify-center bg-destructive/50 text-sm">업로드 실패</div>
                )}
                <button
                  type="button"
                  aria-label="삭제"
                  onClick={() => removeMedia(media.id)}
                  disabled={media.status === "uploading"}
                  className="absolute right-2 top-2 flex size-8 items-center justify-center rounded-full bg-black/75 hover:bg-black/60"
                >
                  <X className="size-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between border-t border-border py-2">
          <input ref={fileInputRef} type="file" accept="image/*,video/*" multiple onChange={handleFileSelect} className="hidden" />
          <button
            type="button"
            aria-label="미디어"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadingMedia.length >= MAX_MEDIA}
            className="-ml-2 flex size-9 items-center justify-center rounded-full text-primary hover:bg-primary/10 disabled:opacity-50"
          >
            <ImageIcon className="size-5" />
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="h-9 rounded-full bg-secondary px-4 font-bold text-secondary-foreground transition-colors hover:bg-secondary/90 disabled:opacity-50"
          >
            게시하기
          </button>
        </div>
      </div>
    </div>
  )
}
