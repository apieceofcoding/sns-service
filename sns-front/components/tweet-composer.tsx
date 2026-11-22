"use client"

import { useState, useRef } from "react"
import { ImageIcon, Smile, MapPin, BarChart3, X, Loader2, User } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Progress } from "@/components/ui/progress"
import { useCreatePost } from "@/hooks/api/use-posts"
import { useMediaUpload } from "@/hooks/api/use-media"
import { useAuth } from "@/hooks/api/use-auth"

const MAX_IMAGES = 4

export function TweetComposer() {
  const [content, setContent] = useState("")
  const { user } = useAuth()
  const createPost = useCreatePost()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const {
    uploadingMedia,
    completedMediaIds,
    uploadMedia,
    removeMedia,
    clearAll,
    isUploading
  } = useMediaUpload()

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
      await createPost.mutateAsync({
        content: content.trim(),
        mediaIds: completedMediaIds,
      })
      setContent("")
      clearAll()
    } catch (error) {
      console.error('Failed to create post:', error)
    }
  }

  const canSubmit = (content.trim() || completedMediaIds.length > 0) && !isUploading

  return (
    <div className="p-4 border-b border-border">
      <div className="flex gap-3">
        <div className="w-12 h-12 rounded-full bg-muted flex-shrink-0 overflow-hidden">
          {user?.profileImageUrl ? (
            <img
              src={user.profileImageUrl}
              alt={user.username}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-muted-foreground font-medium text-lg">
              {user?.username?.charAt(0).toUpperCase() || <User className="w-6 h-6" />}
            </div>
          )}
        </div>
        <div className="flex-1">
          <Textarea
            placeholder="무슨 일이 일어나고 있나요?"
            className="min-h-[120px] resize-none border-none p-0 text-xl focus-visible:ring-0"
            value={content}
            onChange={(e) => setContent(e.target.value)}
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
                        <Loader2 className="w-8 h-8 text-white animate-spin mb-2" />
                        <Progress value={media.progress} className="w-3/4 h-1" />
                        <span className="text-white text-sm mt-1">{media.progress}%</span>
                      </div>
                    )}

                    {media.status === 'error' && (
                      <div className="absolute inset-0 bg-red-500/50 flex items-center justify-center">
                        <span className="text-white text-sm">업로드 실패</span>
                      </div>
                    )}

                    <button
                      onClick={() => removeMedia(media.id)}
                      className="absolute top-2 right-2 w-8 h-8 bg-black/70 hover:bg-black/90 rounded-full flex items-center justify-center transition-colors"
                      disabled={media.status === 'uploading'}
                    >
                      <X className="w-4 h-4 text-white" />
                    </button>
                  </div>
                )
              })}
            </div>
          )}

          <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
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
                className="text-primary hover:bg-primary/10"
                onClick={handleImageButtonClick}
                disabled={uploadingMedia.length >= MAX_IMAGES}
              >
                <ImageIcon className="w-5 h-5" />
              </Button>
              <Button size="icon" variant="ghost" className="text-primary hover:bg-primary/10">
                <Smile className="w-5 h-5" />
              </Button>
              <Button size="icon" variant="ghost" className="text-primary hover:bg-primary/10">
                <MapPin className="w-5 h-5" />
              </Button>
              <Button size="icon" variant="ghost" className="text-primary hover:bg-primary/10">
                <BarChart3 className="w-5 h-5" />
              </Button>
            </div>
            <Button
              className="rounded-full font-bold px-6"
              onClick={handleSubmit}
              disabled={!canSubmit || createPost.isPending}
            >
              {createPost.isPending ? "작성 중..." : isUploading ? "업로드 중..." : "게시하기"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
