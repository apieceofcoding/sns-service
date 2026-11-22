"use client"

import { useState } from "react"
import { usePresignedUrls } from "@/hooks/api/use-media"
import { cn } from "@/lib/utils"
import { VideoPlayer } from "./video-player"
import { ImageLightbox } from "./image-lightbox"

interface MediaGalleryProps {
  mediaIds: number[]
  className?: string
}

export function MediaGallery({ mediaIds, className }: MediaGalleryProps) {
  const queries = usePresignedUrls(mediaIds)
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)

  if (mediaIds.length === 0) return null

  const mediaItems = queries.map((query, index) => ({
    id: mediaIds[index],
    url: query.data?.presignedUrl ?? null,
    mediaType: query.data?.media.mediaType ?? null,
    loading: query.isLoading,
    error: query.isError,
  }))

  const hasOnlyOneVideo = mediaItems.length === 1 && mediaItems[0]?.mediaType === 'VIDEO'

  const getGridClassName = () => {
    if (hasOnlyOneVideo) return "grid-cols-1"
    switch (mediaIds.length) {
      case 1:
        return "grid-cols-1"
      case 2:
        return "grid-cols-2"
      case 3:
        return "grid-cols-2 grid-rows-2"
      case 4:
        return "grid-cols-2 grid-rows-2"
      default:
        return "grid-cols-2"
    }
  }

  const getItemClassName = (index: number) => {
    if (mediaIds.length === 3 && index === 0) {
      return "row-span-2"
    }
    return ""
  }

  const getAspectRatio = (index: number, mediaType: string | null) => {
    if (mediaType === 'VIDEO') {
      return "aspect-video"
    }
    if (mediaIds.length === 1) {
      return "aspect-video"
    }
    if (mediaIds.length === 3 && index === 0) {
      return "aspect-[9/16]"
    }
    return "aspect-square"
  }

  return (
  <>
    <div
      className={cn(
        "grid gap-0.5 rounded-2xl overflow-hidden border border-border",
        getGridClassName(),
        className
      )}
      onClick={(e) => e.stopPropagation()}
    >
      {mediaItems.map((item, index) => (
        <div
          key={item.id}
          className={cn(
            "relative bg-muted overflow-hidden",
            getItemClassName(index),
            getAspectRatio(index, item.mediaType)
          )}
        >
          {item.loading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : item.error ? (
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
              미디어를 불러올 수 없습니다
            </div>
          ) : item.url ? (
            item.mediaType === 'VIDEO' || item.mediaType === 'GIF' ? (
              <VideoPlayer
                src={item.url}
                className="w-full h-full"
                autoPlay={item.mediaType === 'GIF'}
                muted={true}
                loop={item.mediaType === 'GIF'}
                isGif={item.mediaType === 'GIF'}
                autoPlayOnView={item.mediaType === 'VIDEO'}
              />
            ) : (
              <img
                src={item.url}
                alt=""
                className="w-full h-full object-cover hover:opacity-90 transition-opacity cursor-pointer"
                onClick={(e) => {
                  e.stopPropagation()
                  const imageItems = mediaItems.filter(m => m.mediaType === 'IMAGE' && m.url)
                  const imageIndex = imageItems.findIndex(m => m.id === item.id)
                  if (imageIndex !== -1) {
                    setLightboxIndex(imageIndex)
                  }
                }}
              />
            )
          ) : null}
        </div>
      ))}
    </div>

    {lightboxIndex !== null && (
      <ImageLightbox
        images={mediaItems
          .filter(m => m.mediaType === 'IMAGE' && m.url)
          .map(m => ({ id: m.id, url: m.url! }))}
        initialIndex={lightboxIndex}
        onClose={() => setLightboxIndex(null)}
      />
    )}
  </>
  )
}
