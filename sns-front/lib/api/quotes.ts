import { apiClient } from './client'
import type { Quote, QuoteCreateRequest } from '@/lib/types'

export const quotesApi = {
  create: (postId: number, data: QuoteCreateRequest) => {
    return apiClient.post<Quote>(`/api/v1/posts/${postId}/quotes`, data)
  },
}
