"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import { PageHeader } from "@/components/app-shell"
import { UserAvatar } from "@/components/user-avatar"
import { useAuth } from "@/hooks/api/use-auth"
import { useUser, useUserFollowCounts, useUserPosts } from "@/hooks/api/use-users"
import { FollowButton } from "@/components/follow-button"
import { ProfileEditDialog } from "@/components/profile-edit-dialog"

export type UserProfileTab = "posts" | "replies" | "media" | "likes"

interface UserProfileHeaderProps {
  userId: number
  activeTab: UserProfileTab
  onTabChange: (tab: UserProfileTab) => void
}

export function UserProfileHeader({ userId, activeTab, onTabChange }: UserProfileHeaderProps) {
  const router = useRouter()
  const { user: me, isAuthenticated } = useAuth()
  const { data: user, isLoading: isUserLoading } = useUser(userId)
  const { data: followCounts } = useUserFollowCounts(userId)
  const { data: posts } = useUserPosts(userId, isAuthenticated)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)

  const isMe = me?.id === userId

  const postCount = posts?.length ?? 0
  const followingCount = followCounts?.followeesCount ?? 0
  const followerCount = followCounts?.followersCount ?? 0

  if (isUserLoading) return <p className="p-8 text-center text-muted-foreground">불러오는 중...</p>
  if (!user) return <p className="p-8 text-center text-muted-foreground">사용자를 찾을 수 없습니다.</p>

  const tabs: [UserProfileTab, string][] = [
    ["posts", "게시물"],
    ["replies", "답글"],
    ["media", "미디어"],
    ...(isMe ? [["likes", "마음에 들어요"] as [UserProfileTab, string]] : []),
  ]
  const pill = "h-9 rounded-full px-4 font-bold transition-colors disabled:opacity-50"

  return (
    <>
      <PageHeader title={user.username} subtitle={`게시물 ${postCount}개`} onBack={() => router.back()} />

      <div className="aspect-[3/1] bg-[#333639]" />
      <div className="px-4 pt-3">
        <div className="flex items-start justify-between">
          <UserAvatar
            username={user.username}
            imageUrl={user.profileImageUrl}
            className="-mt-[15%] size-[134px] border-4 border-background text-5xl"
          />
          {isMe && (
            <button type="button" onClick={() => setIsEditDialogOpen(true)} className={`${pill} border border-[#536471] hover:bg-foreground/10`}>
              프로필 수정
            </button>
          )}
          <FollowButton userId={userId} />
        </div>

        <div className="mb-3 mt-3 leading-6">
          <h2 className="text-xl font-extrabold">{user.username}</h2>
          <p className="text-muted-foreground">@{user.username}</p>
        </div>

        <div className="mb-3 flex gap-5 text-sm">
          <Link href={`/users/${userId}/following`} className="hover:underline">
            <b>{followingCount.toLocaleString()}</b> <span className="text-muted-foreground">팔로우 중</span>
          </Link>
          <Link href={`/users/${userId}/followers`} className="hover:underline">
            <b>{followerCount.toLocaleString()}</b> <span className="text-muted-foreground">팔로워</span>
          </Link>
        </div>
      </div>

      <div role="tablist" className="flex border-b border-border">
        {tabs.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={activeTab === value}
            onClick={() => onTabChange(value)}
            className="flex h-[53px] flex-1 justify-center px-4 transition-colors hover:bg-foreground/10"
          >
            <span className={cn("relative flex items-center", activeTab === value ? "font-bold" : "font-medium text-muted-foreground")}>
              {label}
              {activeTab === value && <span className="absolute inset-x-0 bottom-0 h-1 rounded-full bg-primary" />}
            </span>
          </button>
        ))}
      </div>

      {isMe && <ProfileEditDialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen} />}
    </>
  )
}
