import { apiClient } from './client'
import type { Post } from '@/lib/types'

export type Feed = 'recommend' | 'timelines'

export interface TimelineResponse {
  posts: Post[]
  nextCursor: number | string | null
  hasMore: boolean
}

export const timelineApi = {
  getTimeline: (cursor?: number | string, limit = 20, feed: Feed = 'timelines') => {
    const params = new URLSearchParams()
    if (cursor !== undefined) {
      params.append('cursor', cursor.toString())
    }
    params.append('limit', limit.toString())
    return apiClient.get<TimelineResponse>(`/api/v1/${feed}?${params.toString()}`)
  },
}
