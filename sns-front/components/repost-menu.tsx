"use client"

import { Repeat2, Quote } from "lucide-react"
import { ActionButton } from "./post-actions"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"
import type { Post } from "@/lib/types"
import { useRepost, useUnrepost } from "@/hooks/api/use-reposts"

interface RepostMenuProps {
  post: Post
  onQuoteClick: () => void
  /** True when this row is my own repost of the post. */
  disableRepost?: boolean
  isReposted?: boolean
}

export function RepostMenu({ post, onQuoteClick, disableRepost = false, isReposted = false }: RepostMenuProps) {
  const repost = useRepost()
  const unrepost = useUnrepost()

  const handleRepost = () => {
    if (post.isRepostedByMe) {
      unrepost.mutate({ postId: post.id, repostId: post.repostIdByMe! })
    } else {
      repost.mutate(post.id)
    }
  }

  const isLoading = repost.isPending || unrepost.isPending

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <ActionButton
          label="재게시"
          tone="repost"
          active={post.isRepostedByMe || isReposted}
          icon={<Repeat2 className="size-[18px]" />}
          count={post.repostCount}
          disabled={isLoading}
        />
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="center"
        className="w-48 rounded-2xl shadow-[0_0_15px_rgba(255,255,255,0.2)]"
        onClick={(e) => e.stopPropagation()}
      >
        <DropdownMenuItem
          onClick={handleRepost}
          disabled={disableRepost && !post.isRepostedByMe}
          className={cn(
            "flex items-center gap-3 px-4 py-3 font-bold cursor-pointer",
            disableRepost && !post.isRepostedByMe && "opacity-50 cursor-not-allowed"
          )}
        >
          <Repeat2 className={cn("w-5 h-5", post.isRepostedByMe && "text-repost")} />
          <span>
            {post.isRepostedByMe ? "재게시 취소" : "재게시"}
          </span>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={onQuoteClick}
          className="flex items-center gap-3 px-4 py-3 font-bold cursor-pointer"
        >
          <Quote className="w-5 h-5" />
          <span>인용하기</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
