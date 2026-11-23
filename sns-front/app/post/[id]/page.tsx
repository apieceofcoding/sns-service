"use client"

import { use, useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, Trash2 } from "lucide-react"
import { format } from "date-fns"
import { ko } from "date-fns/locale"
import { AppShell, PageHeader } from "@/components/app-shell"
import { TweetCard } from "@/components/tweet-card"
import { QuotedTweetCard } from "@/components/quoted-tweet-card"
import { MediaGallery } from "@/components/media-gallery"
import { ProfileAvatar } from "@/components/profile-avatar"
import { UserAvatar } from "@/components/user-avatar"
import { PostActions } from "@/components/post-actions"
import { DeletePostDialog } from "@/components/delete-post-dialog"
import { usePost, useIncrementView } from "@/hooks/api/use-posts"
import { useReplies, useCreateReply } from "@/hooks/api/use-replies"
import { useAuth } from "@/hooks/api/use-auth"
import { asPost } from "@/lib/utils"

export default function PostPage({ params }: { params: Promise<{ id: string }> }) {
  const postId = parseInt(use(params).id, 10)
  const router = useRouter()
  const { user } = useAuth()
  const { data: post, isLoading } = usePost(postId)
  const { data: replies } = useReplies(postId)
  const createReply = useCreateReply()
  const incrementView = useIncrementView()
  const [reply, setReply] = useState("")
  const [deleteOpen, setDeleteOpen] = useState(false)
  const mainRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (postId) incrementView.mutate(postId)
  }, [postId])

  // With a parent shown above, start at this post rather than at the parent.
  useEffect(() => {
    if (post?.parentPost) mainRef.current?.scrollIntoView({ block: "start" })
  }, [post?.parentPost])

  const submitReply = () => {
    if (!reply.trim() || !post) return
    createReply.mutate({ postId: post.id, data: { content: reply.trim() } }, { onSuccess: () => setReply("") })
  }

  return (
    <AppShell>
      <PageHeader title="게시물" onBack={() => router.back()} />

      {isLoading && (
        <div className="flex justify-center p-6">
          <Loader2 className="size-6 animate-spin text-primary" />
        </div>
      )}
      {!isLoading && !post && <p className="p-8 text-center text-muted-foreground">게시물을 찾을 수 없습니다.</p>}

      {post && (
        <>
          {post.parentPost && <TweetCard post={asPost(post.parentPost)} threadLine />}

          <article ref={mainRef} className="scroll-mt-[53px] border-b border-border px-4 pt-3">
            <div className="flex items-center gap-3">
              <ProfileAvatar mediaId={post.userProfileMediaId} username={post.username} />
              <div className="min-w-0 flex-1 leading-5">
                <div className="truncate font-bold">{post.username}</div>
                <div className="truncate text-muted-foreground">@{post.username}</div>
              </div>
              {post.userId === user?.id && (
                <button
                  type="button"
                  aria-label="삭제하기"
                  onClick={() => setDeleteOpen(true)}
                  className="flex size-[34px] items-center justify-center rounded-full text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                >
                  <Trash2 className="size-[18px]" />
                </button>
              )}
            </div>

            {post.content && <p className="mt-3 whitespace-pre-wrap break-words text-[17px] leading-6">{post.content}</p>}
            {post.mediaIds?.length > 0 && <MediaGallery mediaIds={post.mediaIds} className="mt-3" />}
            {post.quotedPost && <QuotedTweetCard post={post.quotedPost} onClick={() => router.push(`/post/${post.quotedPost!.id}`)} />}

            <p className="my-4 text-muted-foreground">
              {format(new Date(post.createdAt), "a h:mm", { locale: ko })} {format(new Date(post.createdAt), "yyyy년 M월 d일")}
              <span className="ml-1 font-bold text-foreground">{post.viewCount.toLocaleString()}</span> 조회수
            </p>

            <div className="border-t border-border pb-3">
              <PostActions post={post} />
            </div>
          </article>

          <div className="flex gap-3 border-b border-border px-4 py-3">
            <UserAvatar username={user?.username} imageUrl={user?.profileImageUrl} />
            <textarea
              rows={1}
              placeholder="답글 게시하기"
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              className="min-w-0 flex-1 resize-none bg-transparent py-2 text-xl outline-none placeholder:text-muted-foreground"
            />
            <button
              type="button"
              onClick={submitReply}
              disabled={!reply.trim() || createReply.isPending}
              className="h-9 self-end rounded-full bg-secondary px-4 font-bold text-secondary-foreground disabled:opacity-50"
            >
              답글
            </button>
          </div>

          {replies?.map((r) => (
            <TweetCard key={r.id} post={asPost(r)} />
          ))}

          <DeletePostDialog postId={post.id} open={deleteOpen} onOpenChange={setDeleteOpen} onDeleted={() => router.back()} />
        </>
      )}
    </AppShell>
  )
}

