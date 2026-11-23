"use client"

import { useState } from "react"
import { usePresignedUrl } from "@/hooks/api/use-media"
import { cn } from "@/lib/utils"

interface ProfileAvatarProps {
  mediaId: number | null | undefined
  username?: string
  size?: "sm" | "md" | "lg"
  className?: string
}

const sizeClasses = {
  sm: "w-5 h-5",
  md: "size-10",
  lg: "w-32 h-32"
}

export function ProfileAvatar({ mediaId, username, size = "md", className }: ProfileAvatarProps) {
  const { data, isLoading } = usePresignedUrl(mediaId)
  const [error, setError] = useState(false)

  const initials = username ? username.charAt(0).toUpperCase() : '?'

  return (
    <div
      className={cn(
        "rounded-full bg-[#333639] flex-shrink-0 overflow-hidden flex items-center justify-center",
        sizeClasses[size],
        className
      )}
    >
      {isLoading ? (
        <div className="w-full h-full bg-muted animate-pulse" />
      ) : data?.presignedUrl && !error ? (
        <img
          src={data.presignedUrl}
          alt={username || 'Profile'}
          className="w-full h-full object-cover"
          onError={() => setError(true)}
        />
      ) : (
        <span className={cn(
          "text-muted-foreground font-medium",
          size === "sm" && "text-xs",
          size === "md" && "text-lg",
          size === "lg" && "text-4xl"
        )}>
          {initials}
        </span>
      )}
    </div>
  )
}
