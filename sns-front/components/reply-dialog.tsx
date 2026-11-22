"use client"

import { useState, useRef } from "react"
import { X, ImageIcon, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Progress } from "@/components/ui/progress"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { formatDistanceToNow } from "date-fns"
import { ko } from "date-fns/locale"
import { useCreateReply } from "@/hooks/api/use-replies"
import { useMediaUpload } from "@/hooks/api/use-media"
import { cn } from "@/lib/utils"
import type { Post } from "@/lib/types"

const MAX_IMAGES = 4

interface ReplyDialogProps {
  post: Post
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ReplyDialog({ post, open, onOpenChange }: ReplyDialogProps) {
  const [content, setContent] = useState("")
  const createReply = useCreateReply()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const {
    uploadingMedia,
    completedMediaIds,
    uploadMedia,
    removeMedia,
    clearAll,
    isUploading
  } = useMediaUpload()

  const formattedDate = formatDistanceToNow(new Date(post.createdAt), {
    addSuffix: false,
    locale: ko,
  })

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return

    const remainingSlots = MAX_IMAGES - uploadingMedia.length
    const filesToUpload = Array.from(files).slice(0, remainingSlots)

    for (const file of filesToUpload) {
      if (file.type.startsWith('image/') || file.type.startsWith('video/')) {
        await uploadMedia(file)
      }
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleImageButtonClick = () => {
    fileInputRef.current?.click()
  }

  const handleSubmit = async () => {
    if (!content.trim() && completedMediaIds.length === 0) return
    if (isUploading) return

    try {
      await createReply.mutateAsync({
        postId: post.id,
        data: {
          content: content.trim(),
          mediaIds: completedMediaIds.length > 0 ? completedMediaIds : undefined,
        },
      })
      setContent("")
      clearAll()
      onOpenChange(false)
    } catch (error) {
      console.error("Failed to create reply:", error)
    }
  }

  const handleClose = () => {
    setContent("")
    clearAll()
    onOpenChange(false)
  }

  const canSubmit = (content.trim() || completedMediaIds.length > 0) && !isUploading

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] p-0 gap-0 bg-background border-border">
        <DialogHeader className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="icon"
              className="rounded-full"
              onClick={handleClose}
            >
              <X className="w-5 h-5" />
            </Button>
            <DialogTitle className="sr-only">답글 달기</DialogTitle>
            <Button
              className="rounded-full font-bold px-5"
              onClick={handleSubmit}
              disabled={!canSubmit || createReply.isPending}
            >
              {createReply.isPending ? "작성 중..." : isUploading ? "업로드 중..." : "답글"}
            </Button>
          </div>
        </DialogHeader>

        <div className="p-4">
          <div className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className="w-10 h-10 rounded-full bg-muted flex-shrink-0" />
              <div className="w-0.5 flex-1 bg-border mt-2 min-h-[20px]" />
            </div>
            <div className="flex-1 min-w-0 pb-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-bold text-sm">{post.username}</span>
                <span className="text-muted-foreground text-sm">
                  @{post.username} · {formattedDate}
                </span>
              </div>
              <p className="text-sm leading-relaxed mb-3">{post.content}</p>
              <p className="text-muted-foreground text-sm">
                <span className="text-primary">@{post.username}</span>
                <span> 님에게 보내는 답글</span>
              </p>
            </div>
          </div>

          <div className="flex gap-3 mt-2">
            <div className="w-10 h-10 rounded-full bg-muted flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <Textarea
                placeholder="답글 게시하기"
                className="min-h-[100px] resize-none border-none p-0 text-lg focus-visible:ring-0 placeholder:text-muted-foreground"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                autoFocus
              />

              {uploadingMedia.length > 0 && (
                <div className={`grid gap-2 mt-3 ${
                  uploadingMedia.length === 1 ? 'grid-cols-1' :
                  uploadingMedia.length === 2 ? 'grid-cols-2' :
                  uploadingMedia.length === 3 ? 'grid-cols-2' :
                  'grid-cols-2'
                }`}>
                  {uploadingMedia.map((media, index) => {
                    const isVideo = media.file.type.startsWith('video/')
                    return (
                      <div
                        key={media.id}
                        className={`relative rounded-xl overflow-hidden bg-muted ${
                          uploadingMedia.length === 3 && index === 0 ? 'row-span-2' : ''
                        } ${isVideo ? 'aspect-video' : 'aspect-square'}`}
                      >
                        {isVideo ? (
                          <video
                            src={media.preview}
                            className="w-full h-full object-cover"
                            muted
                            loop
                            autoPlay
                            playsInline
                          />
                        ) : (
                          <img
                            src={media.preview}
                            alt="업로드 미디어"
                            className="w-full h-full object-cover"
                          />
                        )}

                        {media.status === 'uploading' && (
                          <div className="absolute inset-0 bg-black/50 flex flex-col items-center justify-center">
                            <Loader2 className="w-6 h-6 text-white animate-spin mb-2" />
                            <Progress value={media.progress} className="w-3/4 h-1" />
                            <span className="text-white text-xs mt-1">{media.progress}%</span>
                          </div>
                        )}

                        {media.status === 'error' && (
                          <div className="absolute inset-0 bg-red-500/50 flex items-center justify-center">
                            <span className="text-white text-xs">업로드 실패</span>
                          </div>
                        )}

                        <button
                          onClick={() => removeMedia(media.id)}
                          className="absolute top-1 right-1 w-6 h-6 bg-black/70 hover:bg-black/90 rounded-full flex items-center justify-center transition-colors"
                          disabled={media.status === 'uploading'}
                        >
                          <X className="w-3 h-3 text-white" />
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="px-4 pb-4 pt-2 border-t border-border">
          <div className="flex items-center justify-between">
            <div className="flex gap-1">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,video/*"
                multiple
                onChange={handleFileSelect}
                className="hidden"
              />
              <Button
                size="icon"
                variant="ghost"
                className="text-primary hover:bg-primary/10 h-8 w-8"
                onClick={handleImageButtonClick}
                disabled={uploadingMedia.length >= MAX_IMAGES}
              >
                <ImageIcon className="w-4 h-4" />
              </Button>
            </div>
            <span className={cn(
              "text-sm",
              content.length > 280 ? "text-destructive" : "text-muted-foreground"
            )}>
              {content.length}/280
            </span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
