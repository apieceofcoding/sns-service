"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { MoreHorizontal, Repeat2, Trash2 } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { Post } from "@/lib/types"
import { cn, shortTime } from "@/lib/utils"
import { useIncrementView } from "@/hooks/api/use-posts"
import { useAuth } from "@/hooks/api/use-auth"
import { postsApi } from "@/lib/api/posts"
import { QuotedTweetCard } from "./quoted-tweet-card"
import { MediaGallery } from "./media-gallery"
import { ProfileAvatar } from "./profile-avatar"
import { PostActions } from "./post-actions"
import { DeletePostDialog } from "./delete-post-dialog"

interface TweetCardProps {
  post: Post
  /** Draws a line from the avatar down to the next post, for a parent above its reply. */
  threadLine?: boolean
}

export function TweetCard({ post, threadLine = false }: TweetCardProps) {
  const router = useRouter()
  const { user } = useAuth()
  const incrementView = useIncrementView()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const articleRef = useRef<HTMLElement>(null)

  const shown = post.repostedPost ?? post
  const repostedByMe = !!post.repostedPost && post.repostedBy?.userId === user?.id

  // An impression is recorded once the reader is known and half of the post is on screen.
  useEffect(() => {
    const article = articleRef.current
    if (!article || !user) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        incrementView.mutate(shown.id)
        postsApi.recordAction("impression", shown.id)
        observer.disconnect()
      },
      { threshold: 0.5 },
    )
    observer.observe(article)
    return () => observer.disconnect()
  }, [shown.id, user])

  const open = () => {
    if (user) postsApi.recordAction("click", shown.id)
    router.push(`/post/${shown.id}`)
  }

  const profile = `/users/${shown.userId}`
  const stop = (e: React.MouseEvent) => e.stopPropagation()

  return (
    <article
      ref={articleRef}
      onClick={open}
      className={cn("cursor-pointer px-4 pt-3 transition-colors hover:bg-foreground/[0.03]", !threadLine && "border-b border-border")}
    >
      {post.repostedPost && (
        <div className="mb-1 flex items-center gap-3 text-[13px] font-bold text-muted-foreground">
          <Repeat2 className="ml-6 size-4" />
          {post.repostedBy?.username ?? post.username}님이 재게시함
        </div>
      )}

      <div className="flex gap-3">
        <div className="flex flex-col items-center">
          <Link href={profile} onClick={stop}>
            <ProfileAvatar mediaId={shown.userProfileMediaId} username={shown.username} />
          </Link>
          {threadLine && <div className="mt-1 w-0.5 flex-1 bg-border" />}
        </div>

        <div className="min-w-0 flex-1 pb-3">
          <div className="flex items-start justify-between gap-2">
            <Link href={profile} onClick={stop} className="flex min-w-0 gap-1 leading-5">
              <span className="truncate font-bold hover:underline">{shown.username}</span>
              <span className="truncate text-muted-foreground">@{shown.username}</span>
              <span className="shrink-0 text-muted-foreground">{shortTime(shown.createdAt)}</span>
            </Link>
            {post.userId === user?.id && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    aria-label="더 보기"
                    onClick={stop}
                    className="-m-2 flex size-[34px] items-center justify-center rounded-full text-muted-foreground hover:bg-primary/10 hover:text-primary"
                  >
                    <MoreHorizontal className="size-[18px]" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="rounded-2xl shadow-[0_0_15px_rgba(255,255,255,0.2)]" onClick={stop}>
                  <DropdownMenuItem onClick={() => setDeleteOpen(true)} className="cursor-pointer px-4 py-3 font-bold text-destructive focus:text-destructive">
                    <Trash2 className="size-4" />
                    삭제하기
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>

          {post.parentPost && !threadLine && (
            <p className="text-muted-foreground">
              <span className="text-primary">@{post.parentPost.username}</span> 님에게 보내는 답글
            </p>
          )}

          {shown.content && <p className="whitespace-pre-wrap break-words leading-5">{shown.content}</p>}
          {shown.mediaIds?.length > 0 && <MediaGallery mediaIds={shown.mediaIds} className="mt-3" />}
          {post.quotedPost && <QuotedTweetCard post={post.quotedPost} onClick={() => router.push(`/post/${post.quotedPost!.id}`)} />}

          <PostActions post={shown} repostedByMe={repostedByMe} />
        </div>
      </div>

      <DeletePostDialog postId={post.id} open={deleteOpen} onOpenChange={setDeleteOpen} />
    </article>
  )
}
