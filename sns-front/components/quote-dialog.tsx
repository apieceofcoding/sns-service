"use client"

import { useCreateQuote } from "@/hooks/api/use-quotes"
import type { Post } from "@/lib/types"
import { ComposeDialog } from "./compose-dialog"
import { QuotedTweetCard } from "./quoted-tweet-card"

export function QuoteDialog({ post, open, onOpenChange }: { post: Post; open: boolean; onOpenChange: (open: boolean) => void }) {
  const createQuote = useCreateQuote()

  return (
    <ComposeDialog
      open={open}
      onOpenChange={onOpenChange}
      title="인용하기"
      placeholder="의견을 추가하세요"
      submitLabel="게시하기"
      pending={createQuote.isPending}
      onSubmit={(content, done) => createQuote.mutate({ postId: post.id, data: { content } }, { onSuccess: done })}
      below={<div className="mb-1"><QuotedTweetCard post={post} /></div>}
    />
  )
}
