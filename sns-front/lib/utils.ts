import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { Post } from '@/lib/types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Post time as X shows it: 방금, 5분, 3시간, then 11월 3일. */
export function shortTime(value: string) {
  const date = new Date(value)
  const minutes = Math.floor((Date.now() - date.getTime()) / 60000)
  if (minutes < 1) return "방금"
  if (minutes < 60) return `${minutes}분`
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)}시간`
  const sameYear = date.getFullYear() === new Date().getFullYear()
  return `${sameYear ? "" : `${date.getFullYear()}년 `}${date.getMonth() + 1}월 ${date.getDate()}일`
}

/** Counts as X shows them: 950, 1.2천, 3.4만. */
export function shortCount(value: number) {
  if (!value) return ""
  if (value < 1000) return String(value)
  if (value < 10000) return `${+(value / 1000).toFixed(1)}천`
  return `${+(value / 10000).toFixed(1)}만`
}

/** Parents and replies come without counts; show them as posts with nothing counted yet. */
export function asPost(p: Partial<Post> & Pick<Post, "id" | "userId" | "username" | "content" | "createdAt">): Post {
  return {
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
    ...p,
  } as Post
}
