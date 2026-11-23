"use client"

import { useAuth } from "@/hooks/api/use-auth"
import { useFollow, useIsFollowing, useUnfollow } from "@/hooks/api/use-follows"
import { cn } from "@/lib/utils"

/** X-style follow pill. Hidden for my own account and when signed out. */
export function FollowButton({ userId, className }: { userId: number; className?: string }) {
  const { user: me, isAuthenticated } = useAuth()
  const visible = isAuthenticated && me?.id !== userId
  const { data: isFollowing, isLoading } = useIsFollowing(userId, visible)
  const follow = useFollow()
  const unfollow = useUnfollow()

  if (!visible) return null
  const pending = isLoading || follow.isPending || unfollow.isPending

  return (
    <button
      type="button"
      disabled={pending}
      onClick={(e) => {
        e.preventDefault()
        if (isFollowing) unfollow.mutate(userId)
        else follow.mutate(userId)
      }}
      className={cn(
        "h-9 shrink-0 rounded-full px-4 font-bold transition-colors disabled:opacity-50",
        isFollowing
          ? "border border-[#536471] hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive"
          : "bg-secondary text-secondary-foreground hover:bg-secondary/90",
        className,
      )}
    >
      {isFollowing ? "팔로잉" : "팔로우"}
    </button>
  )
}
