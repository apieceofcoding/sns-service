"use client"

import { useState } from "react"
import { BarChart2, Heart, MessageCircle } from "lucide-react"
import type { Post } from "@/lib/types"
import { cn, shortCount } from "@/lib/utils"
import { useLikePost, useUnlikePost } from "@/hooks/api/use-likes"
import { RepostMenu } from "./repost-menu"
import { QuoteDialog } from "./quote-dialog"
import { ReplyDialog } from "./reply-dialog"

const TONES = {
  primary: "group-hover:bg-primary/10 group-hover:text-primary",
  repost: "group-hover:bg-repost/10 group-hover:text-repost",
  like: "group-hover:bg-like/10 group-hover:text-like",
}

/** Icon with a hover circle and a count, colored like X: blue reply, green repost, pink like. */
export function ActionButton({
  icon,
  count,
  tone = "primary",
  active,
  label,
  ...rest
}: React.ComponentProps<"button"> & {
  icon: React.ReactNode
  count?: number
  tone?: keyof typeof TONES
  active?: boolean
  label: string
}) {
  return (
    <button
      type="button"
      aria-label={label}
      {...rest}
      className={cn(
        "group flex items-center text-[13px] text-muted-foreground transition-colors",
        active && tone === "repost" && "text-repost",
        active && tone === "like" && "text-like",
      )}
    >
      <span className={cn("-m-2 flex size-[34px] items-center justify-center rounded-full transition-colors", TONES[tone])}>
        {icon}
      </span>
      <span className={cn("min-w-6 pl-1 text-left tabular-nums", TONES[tone].split(" ")[1])}>{shortCount(count ?? 0)}</span>
    </button>
  )
}

/** Reply, repost, like and views under a post. */
export function PostActions({ post, repostedByMe = false }: { post: Post; repostedByMe?: boolean }) {
  const likePost = useLikePost()
  const unlikePost = useUnlikePost()
  const [replyOpen, setReplyOpen] = useState(false)
  const [quoteOpen, setQuoteOpen] = useState(false)

  const toggleLike = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (post.isLikedByMe) unlikePost.mutate({ postId: post.id, likeId: post.likeIdByMe! })
    else likePost.mutate(post.id)
  }

  return (
    <div className="mt-3 flex max-w-[425px] justify-between pl-2" onClick={(e) => e.stopPropagation()}>
      <ActionButton
        label="답글"
        icon={<MessageCircle className="size-[18px]" />}
        count={post.replyCount}
        onClick={() => setReplyOpen(true)}
      />
      <RepostMenu post={post} onQuoteClick={() => setQuoteOpen(true)} disableRepost={repostedByMe} isReposted={repostedByMe} />
      <ActionButton
        label="마음에 들어요"
        tone="like"
        active={post.isLikedByMe}
        icon={<Heart className={cn("size-[18px]", post.isLikedByMe && "fill-current")} />}
        count={post.likeCount}
        onClick={toggleLike}
        disabled={likePost.isPending || unlikePost.isPending}
      />
      <ActionButton label="조회수" icon={<BarChart2 className="size-[18px]" />} count={post.viewCount} />

      <ReplyDialog post={post} open={replyOpen} onOpenChange={setReplyOpen} />
      <QuoteDialog post={post} open={quoteOpen} onOpenChange={setQuoteOpen} />
    </div>
  )
}
