"use client"

import { useMemo } from "react"
import { useRouter } from "next/navigation"
import { Play } from "lucide-react"
import { usePresignedUrls } from "@/hooks/api/use-media"
import { cn } from "@/lib/utils"
import type { Post } from "@/lib/types"

interface ProfileMediaGridProps {
  posts: Post[]
  className?: string
}

export function ProfileMediaGrid({ posts, className }: ProfileMediaGridProps) {
  const router = useRouter()

  const postsWithMedia = useMemo(() =>
    posts.filter(post => post.mediaIds && post.mediaIds.length > 0),
    [posts]
  )

  const mediaIds = useMemo(() =>
    postsWithMedia.map(post => post.mediaIds[0]),
    [postsWithMedia]
  )

  const queries = usePresignedUrls(mediaIds)

  const handleClick = (postId: number) => {
    router.push(`/post/${postId}`)
  }

  if (postsWithMedia.length === 0) {
    return null
  }

  return (
    <div className={cn("grid grid-cols-3 gap-0.5", className)}>
      {postsWithMedia.map((post, index) => {
        const query = queries[index]
        const url = query?.data?.presignedUrl ?? null
        const mediaType = query?.data?.media.mediaType ?? null
        const loading = query?.isLoading ?? true
        const error = query?.isError ?? false

        return (
          <div
            key={post.mediaIds[0]}
            className="relative aspect-square bg-muted cursor-pointer overflow-hidden group"
            onClick={() => handleClick(post.id)}
          >
            {loading ? (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            ) : error ? (
              <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs">
                오류
              </div>
            ) : url ? (
              <>
                {mediaType === 'VIDEO' || mediaType === 'GIF' ? (
                  <>
                    <video
                      src={url}
                      className="w-full h-full object-cover"
                      muted
                      playsInline
                      preload="metadata"
                    />
                    <div className="absolute top-2 right-2 bg-black/60 rounded px-1.5 py-0.5 flex items-center gap-1">
                      {mediaType === 'GIF' ? (
                        <span className="text-white text-xs font-bold">GIF</span>
                      ) : (
                        <Play className="w-3 h-3 text-white fill-white" />
                      )}
                    </div>
                  </>
                ) : (
                  <img
                    src={url}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                )}
                <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity" />
              </>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
