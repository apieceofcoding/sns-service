'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { postsApi } from '@/lib/api/posts'
import type { Post, PostCreateRequest } from '@/lib/types'

export function usePost(id: number | null) {
  return useQuery({
    queryKey: ['posts', id],
    queryFn: () => postsApi.getById(id!),
    enabled: !!id,
  })
}

export function useCreatePost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: PostCreateRequest) => postsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] })
      queryClient.invalidateQueries({ queryKey: ['timeline'] })
      queryClient.invalidateQueries({ queryKey: ['profile', 'posts'] })
      toast.success('게시물이 작성되었습니다!')
    },
    onError: () => {
      toast.error('게시물 작성 실패')
    },
  })
}

// A post counts one view per page load.
const viewedPostIds = new Set<number>()

export function useIncrementView() {
  return useMutation({
    mutationFn: (id: number) => {
      if (viewedPostIds.has(id)) {
        return Promise.resolve()
      }
      viewedPostIds.add(id)
      return postsApi.incrementView(id)
    },
  })
}

export function useDeletePost() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => postsApi.delete(id),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['posts'] })
      await queryClient.cancelQueries({ queryKey: ['timeline'] })

      const previousPosts = queryClient.getQueryData(['posts'])
      const previousTimeline = queryClient.getQueryData(['timeline'])

      queryClient.setQueryData(['posts'], (old: Post[] | undefined) =>
        old?.filter((p) => p.id !== id)
      )
      queryClient.setQueryData(['timeline'], (old: Post[] | undefined) =>
        old?.filter((p) => p.id !== id)
      )

      return { previousPosts, previousTimeline }
    },
    onError: (_error, id, context) => {
      if (context?.previousPosts) {
        queryClient.setQueryData(['posts'], context.previousPosts)
      }
      if (context?.previousTimeline) {
        queryClient.setQueryData(['timeline'], context.previousTimeline)
      }
      toast.error('게시물 삭제 실패')
    },
    onSuccess: () => {
      toast.success('게시물이 삭제되었습니다!')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] })
      queryClient.invalidateQueries({ queryKey: ['timeline'] })
      queryClient.invalidateQueries({ queryKey: ['profile', 'posts'] })
    },
  })
}
