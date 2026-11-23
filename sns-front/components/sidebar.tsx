"use client"

import { Bell, Bookmark, Feather, Home, LogOut, Mail, MoreHorizontal, Search, User, Users, CircleEllipsis } from "lucide-react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/api/use-auth"
import { UserAvatar } from "./user-avatar"

// Only 홈 and 프로필 are part of the course; the rest open an empty page so the menu looks complete.
const navItems = [
  { icon: Home, label: "홈", href: "/" },
  { icon: Search, label: "탐색하기", href: "/explore" },
  { icon: Bell, label: "알림", href: "/notifications" },
  { icon: Mail, label: "채팅", href: "/messages" },
  { icon: Bookmark, label: "북마크", href: "/bookmarks" },
  { icon: Users, label: "커뮤니티", href: "/communities" },
  { icon: User, label: "프로필", href: "/profile" },
  { icon: CircleEllipsis, label: "더 보기", href: "/more" },
]

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuth()

  const compose = () => {
    if (pathname === "/") document.getElementById("composer")?.focus()
    else router.push("/?compose")
  }

  return (
    <header className="sticky top-0 flex h-screen w-[88px] shrink-0 flex-col items-end justify-between px-2 xl:w-[275px] xl:items-stretch">
      <div className="flex w-full flex-col items-center xl:items-start">
        <Link href="/" aria-label="홈" className="my-1 flex size-[52px] items-center justify-center rounded-full hover:bg-foreground/10">
          <Feather className="size-7" />
        </Link>

        <nav className="flex w-full flex-col items-center xl:items-start">
          {navItems.map(({ icon: Icon, label, href }) => {
            const active = pathname === href
            return (
              <Link key={href} href={href} className="group py-1">
                <div className="flex items-center gap-5 rounded-full p-3 transition-colors group-hover:bg-foreground/10 xl:pr-6">
                  <Icon className="size-[26px]" strokeWidth={active ? 2.6 : 1.9} />
                  <span className={cn("hidden text-xl xl:inline", active && "font-bold")}>{label}</span>
                </div>
              </Link>
            )
          })}
        </nav>

        <button
          type="button"
          onClick={compose}
          aria-label="게시하기"
          className="my-4 flex size-[52px] items-center justify-center rounded-full bg-secondary font-bold text-secondary-foreground transition-colors hover:bg-secondary/90 xl:w-[90%]"
        >
          <Feather className="size-6 xl:hidden" />
          <span className="hidden text-[17px] xl:inline">게시하기</span>
        </button>
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="my-3 flex items-center gap-3 rounded-full p-3 transition-colors hover:bg-foreground/10"
          >
            <UserAvatar username={user?.username} imageUrl={user?.profileImageUrl} />
            <div className="hidden min-w-0 flex-1 text-left leading-5 xl:block">
              <div className="truncate font-bold">{user?.username}</div>
              <div className="truncate text-muted-foreground">@{user?.username}</div>
            </div>
            <MoreHorizontal className="hidden size-5 xl:block" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64 rounded-2xl py-3 shadow-[0_0_15px_rgba(255,255,255,0.2)]">
          <DropdownMenuItem onClick={() => logout()} className="cursor-pointer px-4 py-3 font-bold">
            <LogOut className="size-4" />@{user?.username} 계정에서 로그아웃
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  )
}
