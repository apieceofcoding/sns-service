"use client"

import { useState } from "react"
import { ArrowLeft } from "lucide-react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuth } from "@/hooks/api/use-auth"
import { useFollowCounts } from "@/hooks/api/use-follows"
import { useMyPosts } from "@/hooks/api/use-profile"
import { ProfileEditDialog } from "@/components/profile-edit-dialog"
import type { ProfileTab } from "@/app/profile/page"

interface ProfileHeaderProps {
  activeTab: ProfileTab
  onTabChange: (tab: ProfileTab) => void
}

export function ProfileHeader({ activeTab, onTabChange }: ProfileHeaderProps) {
  const router = useRouter()
  const { user, isAuthenticated } = useAuth()
  const { data: followCounts } = useFollowCounts(isAuthenticated)
  const { data: posts } = useMyPosts(isAuthenticated)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)

  const postCount = posts?.length ?? 0
  const followingCount = followCounts?.followeesCount ?? 0
  const followerCount = followCounts?.followersCount ?? 0

  return (
    <>
      <div className="sticky top-0 z-10 bg-background/80 backdrop-blur-md border-b border-border">
        <div className="flex items-center gap-4 p-4">
          <Button
            variant="ghost"
            size="icon"
            className="rounded-full"
            onClick={() => router.back()}
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-xl font-bold">{user?.username ?? "사용자"}</h1>
            <div className="text-sm text-muted-foreground">{postCount}개 게시물</div>
          </div>
        </div>
      </div>

      <div>
        <div className="h-48 bg-gradient-to-r from-primary/20 to-primary/40" />
        <div className="px-4">
          <div className="flex justify-between items-start -mt-16 mb-4">
            <div className="w-32 h-32 rounded-full border-4 border-background bg-muted overflow-hidden">
              {user?.profileImageUrl ? (
                <img
                  src={user.profileImageUrl}
                  alt={user.username}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-4xl text-muted-foreground font-medium">
                  {user?.username?.charAt(0).toUpperCase() || '?'}
                </div>
              )}
            </div>
            <Button
              variant="outline"
              className="mt-20 rounded-full font-bold bg-transparent"
              onClick={() => setIsEditDialogOpen(true)}
            >
              프로필 수정
            </Button>
          </div>

          <div className="mb-4">
            <h2 className="text-2xl font-bold">{user?.username ?? "사용자"}</h2>
            <div className="text-muted-foreground">@{user?.username ?? "username"}</div>
          </div>

          <div className="flex gap-6 mb-4 text-sm">
            <div>
              <span className="font-bold text-foreground">{followingCount.toLocaleString()}</span>
              <span className="text-muted-foreground ml-1">팔로잉</span>
            </div>
            <div>
              <span className="font-bold text-foreground">{followerCount.toLocaleString()}</span>
              <span className="text-muted-foreground ml-1">팔로워</span>
            </div>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={(value) => onTabChange(value as ProfileTab)} className="w-full">
          <TabsList className="w-full justify-start rounded-none border-b border-border bg-transparent h-auto p-0">
            <TabsTrigger
              value="posts"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent flex-1"
            >
              게시글
            </TabsTrigger>
            <TabsTrigger
              value="replies"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent flex-1"
            >
              답글
            </TabsTrigger>
            <TabsTrigger
              value="media"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent flex-1"
            >
              미디어
            </TabsTrigger>
            <TabsTrigger
              value="likes"
              className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent flex-1"
            >
              마음에 들어요
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <ProfileEditDialog
        open={isEditDialogOpen}
        onOpenChange={setIsEditDialogOpen}
      />
    </>
  )
}
