export interface Post {
  id: number
  content: string
  userId: number
  username: string
  userProfileMediaId: number | null
  repostCount: number
  likeCount: number
  replyCount: number
  viewCount: number
  mediaIds: number[]
  parentId: number | null
  quoteId: number | null
  repostId: number | null
  createdAt: string
  modifiedAt: string
  isLikedByMe: boolean
  likeIdByMe: number | null
  isRepostedByMe: boolean
  repostIdByMe: number | null
  repostedPost?: Post | null
  quotedPost?: Post | null
  parentPost?: Post | null
  repostedBy?: {
    userId: number
    username: string
  } | null
}

export interface PostCreateRequest {
  content: string
  mediaIds: number[]
}
