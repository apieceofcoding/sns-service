"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import { AppShell, PageHeader } from "@/components/app-shell"
import { FollowButton } from "@/components/follow-button"
import { UserAvatar } from "@/components/user-avatar"
import { useUser, useUserFollows } from "@/hooks/api/use-users"
import type { FollowListKind } from "@/lib/api/users"
import { cn } from "@/lib/utils"

const TABS: [FollowListKind, string][] = [
  ["followers", "팔로워"],
  ["following", "팔로우 중"],
]

const EMPTY: Record<FollowListKind, [string, string]> = {
  followers: ["아직 팔로워가 없습니다", "이 계정을 팔로우하는 사람이 여기에 표시됩니다."],
  following: ["아직 팔로우하는 계정이 없습니다", "이 계정이 팔로우하는 사람이 여기에 표시됩니다."],
}

/** X-style followers and following pages: tabs on top, one row per account. */
export function FollowList({ userId, kind }: { userId: number; kind: FollowListKind }) {
  const router = useRouter()
  const { data: user } = useUser(userId)
  const { data: users, isLoading } = useUserFollows(userId, kind)

  return (
    <AppShell>
      <PageHeader title={user?.username ?? ""} subtitle={user ? `@${user.username}` : undefined} onBack={() => router.back()} />
      <div role="tablist" className="flex border-b border-border">
        {TABS.map(([value, label]) => (
          <Link
            key={value}
            href={`/users/${userId}/${value}`}
            replace
            role="tab"
            aria-selected={kind === value}
            className="flex h-[53px] flex-1 justify-center px-4 transition-colors hover:bg-foreground/10"
          >
            <span className={cn("relative flex items-center", kind === value ? "font-bold" : "font-medium text-muted-foreground")}>
              {label}
              {kind === value && <span className="absolute inset-x-0 bottom-0 h-1 rounded-full bg-primary" />}
            </span>
          </Link>
        ))}
      </div>

      {isLoading && (
        <div className="flex justify-center p-6">
          <Loader2 className="size-6 animate-spin text-primary" />
        </div>
      )}

      {!isLoading && users?.length === 0 && (
        <div className="mx-auto max-w-[400px] px-8 py-16">
          <h2 className="text-[31px] font-extrabold leading-9">{EMPTY[kind][0]}</h2>
          <p className="mt-2 text-muted-foreground">{EMPTY[kind][1]}</p>
        </div>
      )}

      {users?.map((u) => (
        <Link key={u.id} href={`/users/${u.id}`} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-foreground/[0.03]">
          <UserAvatar username={u.username} imageUrl={u.profileImageUrl} />
          <div className="min-w-0 flex-1 leading-5">
            <p className="truncate font-bold hover:underline">{u.username}</p>
            <p className="truncate text-muted-foreground">@{u.username}</p>
          </div>
          <FollowButton userId={u.id} />
        </Link>
      ))}
    </AppShell>
  )
}
