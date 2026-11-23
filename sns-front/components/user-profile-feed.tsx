"use client"

import { Loader2 } from "lucide-react"
import { TweetCard } from "./tweet-card"
import { ProfileMediaGrid } from "./profile-media-grid"
import { useUserPosts, useUserReplies } from "@/hooks/api/use-users"
import { useMyLikes } from "@/hooks/api/use-profile"
import { useAuth } from "@/hooks/api/use-auth"
import { asPost } from "@/lib/utils"
import type { Post } from "@/lib/types"
import type { UserProfileTab } from "./user-profile-header"

const EMPTY: Record<UserProfileTab, string> = {
  posts: "아직 작성한 게시물이 없습니다.",
  replies: "아직 작성한 답글이 없습니다.",
  media: "아직 미디어가 없습니다.",
  likes: "아직 마음에 들어 한 게시물이 없습니다.",
}

export function UserProfileFeed({ userId, activeTab }: { userId: number; activeTab: UserProfileTab }) {
  const { isAuthenticated } = useAuth()
  const posts = useUserPosts(userId, isAuthenticated && activeTab !== "replies" && activeTab !== "likes")
  const replies = useUserReplies(userId, isAuthenticated && activeTab === "replies")
  const likes = useMyLikes(isAuthenticated && activeTab === "likes")

  const query = activeTab === "replies" ? replies : activeTab === "likes" ? likes : posts
  if (query.isLoading) {
    return (
      <div className="flex justify-center p-6">
        <Loader2 className="size-6 animate-spin text-primary" />
      </div>
    )
  }
  if (query.error) return <p className="p-8 text-center text-muted-foreground">불러올 수 없습니다.</p>

  const items: Post[] =
    activeTab === "replies" ? (replies.data ?? []).map(asPost) : activeTab === "likes" ? (likes.data ?? []) : (posts.data ?? [])
  const shown = activeTab === "media" ? items.filter((p) => p.mediaIds?.length > 0) : items

  if (shown.length === 0) return <p className="p-8 text-center text-muted-foreground">{EMPTY[activeTab]}</p>
  if (activeTab === "media") return <ProfileMediaGrid posts={shown} />
  return shown.map((post) => <TweetCard key={post.id} post={post} />)
}
