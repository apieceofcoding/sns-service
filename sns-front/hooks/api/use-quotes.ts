'use client'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { quotesApi } from '@/lib/api/quotes'
import type { QuoteCreateRequest } from '@/lib/types'

export function useCreateQuote() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ postId, data }: { postId: number; data: QuoteCreateRequest }) =>
      quotesApi.create(postId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] })
      queryClient.invalidateQueries({ queryKey: ['timeline'] })
      toast.success('인용글이 작성되었습니다!')
    },
    onError: () => {
      toast.error('인용글 작성 실패')
    },
  })
}
