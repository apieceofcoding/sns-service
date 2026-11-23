"use client"

import { useCreateReply } from "@/hooks/api/use-replies"
import { shortTime } from "@/lib/utils"
import type { Post } from "@/lib/types"
import { ComposeDialog } from "./compose-dialog"
import { ProfileAvatar } from "./profile-avatar"

export function ReplyDialog({ post, open, onOpenChange }: { post: Post; open: boolean; onOpenChange: (open: boolean) => void }) {
  const createReply = useCreateReply()

  const original = (
    <div className="flex gap-3 px-4 pt-1">
      <div className="flex flex-col items-center">
        <ProfileAvatar mediaId={post.userProfileMediaId} username={post.username} />
        <div className="my-1 w-0.5 flex-1 bg-border" />
      </div>
      <div className="min-w-0 flex-1 pb-4">
        <p className="leading-5">
          <b>{post.username}</b> <span className="text-muted-foreground">@{post.username} {shortTime(post.createdAt)}</span>
        </p>
        <p className="whitespace-pre-wrap break-words">{post.content}</p>
        <p className="mt-3 text-muted-foreground">
          <span className="text-primary">@{post.username}</span> 님에게 보내는 답글
        </p>
      </div>
    </div>
  )

  return (
    <ComposeDialog
      open={open}
      onOpenChange={onOpenChange}
      title="답글 달기"
      placeholder="답글 게시하기"
      submitLabel="답글"
      pending={createReply.isPending}
      onSubmit={(content, done) => createReply.mutate({ postId: post.id, data: { content } }, { onSuccess: done })}
      above={original}
    />
  )
}
