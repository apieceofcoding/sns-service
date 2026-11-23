"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { Loader2 } from "lucide-react"
import { AppShell } from "@/components/app-shell"
import { useAuth } from "@/hooks/api/use-auth"

/** My profile is the user page for my ID. */
export default function ProfilePage() {
  const router = useRouter()
  const { user, isLoading } = useAuth()

  useEffect(() => {
    if (user) router.replace(`/users/${user.id}`)
  }, [user, router])

  return (
    <AppShell>
      {isLoading || user ? (
        <div className="flex justify-center p-6">
          <Loader2 className="size-6 animate-spin text-primary" />
        </div>
      ) : (
        <p className="p-8 text-center text-muted-foreground">로그인 정보를 불러올 수 없습니다.</p>
      )}
    </AppShell>
  )
}
