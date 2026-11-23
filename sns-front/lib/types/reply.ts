export interface Reply {
  id: number
  content: string
  userId: number
  username: string
  userProfileMediaId: number | null
  parentId: number
  mediaIds?: number[]
  createdAt: string
  modifiedAt: string
}

export interface ReplyCreateRequest {
  content: string
  mediaIds?: number[]
}
