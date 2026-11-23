import { apiClient } from './client'
import type {
  MediaInitRequest,
  MediaInitResponse,
  MediaUploadedRequest,
  MediaResponse,
  PresignedUrlResponse,
} from '@/lib/types'

export const mediaApi = {
  initUpload: (data: MediaInitRequest) => {
    return apiClient.post<MediaInitResponse>('/api/v1/media/init', data)
  },

  uploadComplete: (data: MediaUploadedRequest) => {
    return apiClient.post<MediaResponse>('/api/v1/media/uploaded', data)
  },

  getPresignedUrl: (id: number) => {
    return apiClient.get<PresignedUrlResponse>(`/api/v1/media/${id}/presigned-url`)
  },
}
