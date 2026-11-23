"use client"

import { use, useState } from "react"
import { AppShell } from "@/components/app-shell"
import { UserProfileHeader, type UserProfileTab } from "@/components/user-profile-header"
import { UserProfileFeed } from "@/components/user-profile-feed"

export default function UserProfilePage({ params }: { params: Promise<{ userId: string }> }) {
  const userId = parseInt(use(params).userId, 10)
  const [activeTab, setActiveTab] = useState<UserProfileTab>("posts")

  return (
    <AppShell>
      {isNaN(userId) ? (
        <p className="p-8 text-center text-muted-foreground">잘못된 사용자 ID입니다.</p>
      ) : (
        <>
          <UserProfileHeader userId={userId} activeTab={activeTab} onTabChange={setActiveTab} />
          <UserProfileFeed userId={userId} activeTab={activeTab} />
        </>
      )}
    </AppShell>
  )
}
