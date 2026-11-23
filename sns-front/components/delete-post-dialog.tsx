"use client"

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
import { useDeletePost } from "@/hooks/api/use-posts"

export function DeletePostDialog({
  postId,
  open,
  onOpenChange,
  onDeleted,
}: {
  postId: number
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted?: () => void
}) {
  const deletePost = useDeletePost()

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-[320px] rounded-2xl border-none p-8" onClick={(e) => e.stopPropagation()}>
        <AlertDialogHeader>
          <AlertDialogTitle className="text-xl">게시물을 삭제할까요?</AlertDialogTitle>
          <AlertDialogDescription>삭제한 게시물은 되돌릴 수 없습니다.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="flex-col gap-3 sm:flex-col">
          <AlertDialogAction
            onClick={() => deletePost.mutate(postId, { onSuccess: onDeleted })}
            className="h-11 rounded-full bg-destructive font-bold text-white hover:bg-destructive/90"
          >
            삭제하기
          </AlertDialogAction>
          <AlertDialogCancel className="h-11 rounded-full font-bold">취소</AlertDialogCancel>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
