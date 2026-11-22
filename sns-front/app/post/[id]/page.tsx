"use client"

import { use, useState, useEffect, useRef } from "react"
import { ArrowLeft, Heart, MessageCircle, Share, MoreHorizontal, Bookmark, Repeat2, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Sidebar } from "@/components/sidebar"
import { PostDetailSidebar } from "@/components/post-detail-sidebar"
import { TweetCard } from "@/components/tweet-card"
import { QuotedTweetCard } from "@/components/quoted-tweet-card"
import { RepostMenu } from "@/components/repost-menu"
import { QuoteDialog } from "@/components/quote-dialog"
import { MediaGallery } from "@/components/media-gallery"
import { ProfileAvatar } from "@/components/profile-avatar"
import { usePost, useDeletePost, useIncrementView } from "@/hooks/api/use-posts"
import { useReplies, useCreateReply } from "@/hooks/api/use-replies"
import { useLikePost, useUnlikePost } from "@/hooks/api/use-likes"
import { useRouter } from "next/navigation"
import { format } from "date-fns"
import { ko } from "date-fns/locale"
import { cn } from "@/lib/utils"
import { Loader2 } from "lucide-react"

interface PostPageProps {
  params: Promise<{ id: string }>
}

export default function PostPage({ params }: PostPageProps) {
  const { id } = use(params)
  const postId = parseInt(id, 10)
  const router = useRouter()

  const { data: post, isLoading: postLoading } = usePost(postId)
  const { data: replies, isLoading: repliesLoading } = useReplies(postId)

  const [replyContent, setReplyContent] = useState("")
  const [quoteDialogOpen, setQuoteDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const mainPostRef = useRef<HTMLElement>(null)

  const createReply = useCreateReply()
  const likePost = useLikePost()
  const unlikePost = useUnlikePost()
  const deletePost = useDeletePost()
  const incrementView = useIncrementView()

  useEffect(() => {
    if (postId) {
      incrementView.mutate(postId)
    }
  }, [postId])

  const handleReplySubmit = async () => {
    if (!replyContent.trim() || !post) return

    try {
      await createReply.mutateAsync({
        postId: post.id,
        data: { content: replyContent.trim() },
      })
      setReplyContent("")
    } catch (error) {
      console.error("Failed to create reply:", error)
    }
  }

  const handleLike = () => {
    if (!post) return
    if (post.isLikedByMe) {
      unlikePost.mutate({ postId: post.id, likeId: post.likeIdByMe! })
    } else {
      likePost.mutate(post.id)
    }
  }

  useEffect(() => {
    if (post?.parentPost && mainPostRef.current) {
      setTimeout(() => {
        mainPostRef.current?.scrollIntoView({ behavior: "instant", block: "start" })
      }, 100)
    }
  }, [post?.parentPost])

  if (postLoading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <div className="flex-1 flex justify-center">
          <main className="w-full max-w-2xl border-x border-border">
            <div className="flex items-center justify-center h-screen">
              <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          </main>
          <aside className="hidden lg:block w-80 xl:w-96 flex-shrink-0">
            <div className="sticky top-0">
              <PostDetailSidebar />
            </div>
          </aside>
        </div>
      </div>
    )
  }

  if (!post) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <div className="flex-1 flex justify-center">
          <main className="w-full max-w-2xl border-x border-border">
            <div className="flex flex-col items-center justify-center h-screen gap-4">
              <p className="text-muted-foreground">게시물을 찾을 수 없습니다.</p>
              <Button variant="outline" onClick={() => router.back()}>
                돌아가기
              </Button>
            </div>
          </main>
          <aside className="hidden lg:block w-80 xl:w-96 flex-shrink-0">
            <div className="sticky top-0">
              <PostDetailSidebar />
            </div>
          </aside>
        </div>
      </div>
    )
  }

  const formattedTime = format(new Date(post.createdAt), "a h:mm", { locale: ko })
  const formattedDate = format(new Date(post.createdAt), "yyyy년 M월 d일", { locale: ko })

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 flex justify-center">
        <main className="w-full max-w-2xl border-x border-border">
          <div className="sticky top-0 z-10 bg-background/80 backdrop-blur-md border-b border-border">
            <div className="flex items-center gap-6 px-4 py-3">
              <Button
                variant="ghost"
                size="icon"
                className="rounded-full"
                onClick={() => router.back()}
              >
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <h1 className="text-xl font-bold">게시물</h1>
            </div>
          </div>

          {post.parentPost && (
            <article
              className="border-b border-border hover:bg-accent/30 transition-colors cursor-pointer"
              onClick={() => router.push(`/post/${post.parentPost!.id}`)}
            >
              <div className="flex gap-3 p-4">
                <div className="flex flex-col items-center">
                  <ProfileAvatar
                    mediaId={post.parentPost.userProfileMediaId}
                    username={post.parentPost.username}
                    size="md"
                  />
                  <div className="w-0.5 flex-1 bg-border mt-2" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-1">
                      <span className="font-bold hover:underline">
                        {post.parentPost.username}
                      </span>
                      <span className="text-muted-foreground">@{post.parentPost.username}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="flex-shrink-0 -mr-2 rounded-full hover:bg-primary/10 hover:text-primary"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreHorizontal className="w-5 h-5" />
                    </Button>
                  </div>
                  <p className="leading-relaxed whitespace-pre-wrap mb-3">{post.parentPost.content}</p>
                  {post.parentPost.mediaIds && post.parentPost.mediaIds.length > 0 && (
                    <div className="mb-3">
                      <MediaGallery mediaIds={post.parentPost.mediaIds} />
                    </div>
                  )}
                  <div className="flex items-center gap-6 -ml-2 text-muted-foreground">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="hover:text-primary hover:bg-primary/10 gap-2 rounded-full"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MessageCircle className="w-[18px] h-[18px]" />
                      <span className="text-sm tabular-nums">{post.parentPost.replyCount || ""}</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="hover:text-green-500 hover:bg-green-500/10 gap-2 rounded-full"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Repeat2 className="w-[18px] h-[18px]" />
                      <span className="text-sm tabular-nums">{post.parentPost.repostCount || ""}</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="hover:text-rose-500 hover:bg-rose-500/10 gap-2 rounded-full"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Heart className="w-[18px] h-[18px]" />
                      <span className="text-sm tabular-nums">{post.parentPost.likeCount || ""}</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="hover:text-primary hover:bg-primary/10 rounded-full"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Share className="w-[18px] h-[18px]" />
                    </Button>
                  </div>
                </div>
              </div>
            </article>
          )}

          <article ref={mainPostRef} className="border-b border-border">
            <div className="p-4">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <ProfileAvatar
                    mediaId={post.userProfileMediaId}
                    username={post.username}
                    size="md"
                  />
                  <div>
                    <div className="font-bold hover:underline cursor-pointer">{post.username}</div>
                    <div className="text-muted-foreground text-sm">@{post.username}</div>
                  </div>
                </div>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="rounded-full">
                      <MoreHorizontal className="w-5 h-5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    <DropdownMenuItem
                      onClick={() => setDeleteDialogOpen(true)}
                      className="text-destructive focus:text-destructive cursor-pointer"
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      삭제
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              <p className="text-xl leading-relaxed whitespace-pre-wrap mb-4">{post.content}</p>

              {post.mediaIds && post.mediaIds.length > 0 && (
                <div className="mb-4">
                  <MediaGallery mediaIds={post.mediaIds} />
                </div>
              )}

              {post.quotedPost && (
                <QuotedTweetCard
                  post={post.quotedPost}
                  onClick={() => router.push(`/post/${post.quotedPost!.id}`)}
                />
              )}

              <div className="flex items-center gap-1 text-muted-foreground text-sm py-4 border-b border-border">
                <span>{formattedTime}</span>
                <span>·</span>
                <span>{formattedDate}</span>
                <span>·</span>
                <span className="text-foreground font-semibold">{post.viewCount.toLocaleString()}</span>
                <span>조회수</span>
              </div>

              <div className="flex items-center gap-4 py-4 border-b border-border text-sm">
                <button className="hover:underline">
                  <span className="font-bold">{post.repostCount}</span>
                  <span className="text-muted-foreground ml-1">재게시</span>
                </button>
                <button className="hover:underline">
                  <span className="font-bold">{post.likeCount}</span>
                  <span className="text-muted-foreground ml-1">마음에 들어요</span>
                </button>
                <button className="hover:underline">
                  <span className="font-bold">{post.replyCount}</span>
                  <span className="text-muted-foreground ml-1">답글</span>
                </button>
              </div>

              <div className="flex items-center justify-around py-2 border-b border-border">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-full gap-2"
                >
                  <MessageCircle className="w-6 h-6" />
                  <span className="text-sm tabular-nums">{post.replyCount || ""}</span>
                </Button>

                <RepostMenu post={post} onQuoteClick={() => setQuoteDialogOpen(true)} />

                <Button
                  variant="ghost"
                  size="sm"
                  className={cn(
                    "text-muted-foreground hover:text-rose-500 hover:bg-rose-500/10 rounded-full gap-2",
                    post.isLikedByMe && "text-rose-500"
                  )}
                  onClick={handleLike}
                  disabled={likePost.isPending || unlikePost.isPending}
                >
                  <Heart className={cn("w-6 h-6", post.isLikedByMe && "fill-current")} />
                  <span className="text-sm tabular-nums">{post.likeCount || ""}</span>
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-full"
                >
                  <Bookmark className="w-6 h-6" />
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-full"
                >
                  <Share className="w-6 h-6" />
                </Button>
              </div>
            </div>

            <div className="p-4 border-b border-border">
              <div className="flex gap-3">
                <div className="w-10 h-10 rounded-full bg-muted flex-shrink-0" />
                <div className="flex-1">
                  <Textarea
                    placeholder="답글 게시하기"
                    className="min-h-[60px] resize-none border-none p-0 text-lg focus-visible:ring-0 placeholder:text-muted-foreground"
                    value={replyContent}
                    onChange={(e) => setReplyContent(e.target.value)}
                  />
                  <div className="flex justify-end mt-2">
                    <Button
                      className="rounded-full font-bold px-5"
                      onClick={handleReplySubmit}
                      disabled={!replyContent.trim() || createReply.isPending}
                    >
                      {createReply.isPending ? "작성 중..." : "답글"}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </article>

          <div>
            {repliesLoading && (
              <div className="flex items-center justify-center p-8">
                <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
              </div>
            )}

            {replies && replies.length === 0 && (
              <div className="text-center p-8 text-muted-foreground">
                <p>아직 답글이 없습니다.</p>
                <p className="text-sm mt-2">첫 번째 답글을 남겨보세요!</p>
              </div>
            )}

            {replies?.map((reply) => (
              <TweetCard
                key={reply.id}
                post={{
                  ...reply,
                  repostCount: 0,
                  likeCount: 0,
                  replyCount: 0,
                  viewCount: 0,
                  mediaIds: [],
                  quoteId: null,
                  repostId: null,
                  isLikedByMe: false,
                  likeIdByMe: null,
                  isRepostedByMe: false,
                  repostIdByMe: null,
                }}
              />
            ))}
          </div>
        </main>
        <aside className="hidden lg:block w-80 xl:w-96 flex-shrink-0">
          <div className="sticky top-0">
            <PostDetailSidebar />
          </div>
        </aside>
      </div>

      <QuoteDialog
        post={post}
        open={quoteDialogOpen}
        onOpenChange={setQuoteDialogOpen}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>게시물을 삭제하시겠습니까?</AlertDialogTitle>
            <AlertDialogDescription>
              이 작업은 되돌릴 수 없습니다. 게시물이 영구적으로 삭제됩니다.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>취소</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                deletePost.mutate(post.id, {
                  onSuccess: () => router.back(),
                })
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              삭제
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
