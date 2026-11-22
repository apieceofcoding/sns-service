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
  repostedPost?: Post | null       // 재게시의 원본 게시물
  quotedPost?: Post | null         // 인용된 게시물
  parentPost?: Post | null         // 답글의 부모 게시물
  repostedBy?: {
    userId: number
    username: string
  } | null
}

export interface PostCreateRequest {
  content: string
  mediaIds: number[]
}

export interface PostUpdateRequest {
  content: string
}
