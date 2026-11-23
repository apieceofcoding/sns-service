'use client'

import { useState, useCallback } from 'react'
import { useQuery, useQueries } from '@tanstack/react-query'
import { toast } from 'sonner'
import { mediaApi } from '@/lib/api/media'
import type { MediaType, MediaInitResponse, MediaUploadPart } from '@/lib/types'

export function usePresignedUrl(mediaId: number | null | undefined) {
  return useQuery({
    queryKey: ['media', 'presigned', mediaId],
    queryFn: () => mediaApi.getPresignedUrl(mediaId!),
    enabled: !!mediaId,
    staleTime: 5 * 60 * 1000,
  })
}

export function usePresignedUrls(mediaIds: number[]) {
  return useQueries({
    queries: mediaIds.map(id => ({
      queryKey: ['media', 'presigned', id],
      queryFn: () => mediaApi.getPresignedUrl(id),
      staleTime: 5 * 60 * 1000,
    })),
  })
}

export interface UploadingMedia {
  id: number
  file: File
  preview: string
  progress: number
  status: 'uploading' | 'completed' | 'error'
}

const CHUNK_SIZE = 8 * 1024 * 1024 // must match the server's part size

function getMediaType(file: File): MediaType {
  if (file.type.startsWith('video/')) {
    return 'VIDEO'
  }
  return 'IMAGE'
}

export function useMediaUpload() {
  const [uploadingMedia, setUploadingMedia] = useState<UploadingMedia[]>([])
  const [completedMediaIds, setCompletedMediaIds] = useState<number[]>([])

  const uploadMedia = useCallback(async (file: File): Promise<number | null> => {
    const mediaType = getMediaType(file)
    const preview = URL.createObjectURL(file)

    const tempId = Date.now()
    setUploadingMedia(prev => [...prev, {
      id: tempId,
      file,
      preview,
      progress: 0,
      status: 'uploading'
    }])

    try {
      const initResponse = await mediaApi.initUpload({
        mediaType,
        fileSize: file.size
      })

      const mediaId = initResponse.id

      setUploadingMedia(prev => prev.map(m =>
        m.id === tempId ? { ...m, id: mediaId } : m
      ))

      let parts: MediaUploadPart[] = []

      if (initResponse.presignedUrlParts && initResponse.presignedUrlParts.length > 0) {
        parts = await uploadMultipart(file, initResponse, (progress) => {
          setUploadingMedia(prev => prev.map(m =>
            m.id === mediaId ? { ...m, progress } : m
          ))
        })
      } else if (initResponse.presignedUrl) {
        await uploadSinglePart(file, initResponse.presignedUrl, (progress) => {
          setUploadingMedia(prev => prev.map(m =>
            m.id === mediaId ? { ...m, progress } : m
          ))
        })
      }

      await mediaApi.uploadComplete({
        mediaId,
        parts: parts.length > 0 ? parts : undefined
      })

      setUploadingMedia(prev => prev.map(m =>
        m.id === mediaId ? { ...m, progress: 100, status: 'completed' } : m
      ))
      setCompletedMediaIds(prev => [...prev, mediaId])

      return mediaId
    } catch {
      toast.error('미디어 업로드 실패')
      setUploadingMedia(prev => prev.map(m =>
        m.id === tempId ? { ...m, status: 'error' } : m
      ))
      return null
    }
  }, [])

  const removeMedia = useCallback((id: number) => {
    setUploadingMedia(prev => {
      const media = prev.find(m => m.id === id)
      if (media) {
        URL.revokeObjectURL(media.preview)
      }
      return prev.filter(m => m.id !== id)
    })
    setCompletedMediaIds(prev => prev.filter(mid => mid !== id))
  }, [])

  const clearAll = useCallback(() => {
    uploadingMedia.forEach(m => URL.revokeObjectURL(m.preview))
    setUploadingMedia([])
    setCompletedMediaIds([])
  }, [uploadingMedia])

  const isUploading = uploadingMedia.some(m => m.status === 'uploading')

  return {
    uploadingMedia,
    completedMediaIds,
    uploadMedia,
    removeMedia,
    clearAll,
    isUploading
  }
}

async function uploadSinglePart(
  file: File,
  presignedUrl: string,
  onProgress: (progress: number) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const progress = Math.round((e.loaded / e.total) * 100)
        onProgress(progress)
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve()
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`))
      }
    })

    xhr.addEventListener('error', () => reject(new Error('Upload failed')))

    xhr.open('PUT', presignedUrl)
    xhr.setRequestHeader('Content-Type', file.type)
    xhr.send(file)
  })
}

async function uploadMultipart(
  file: File,
  initResponse: MediaInitResponse,
  onProgress: (progress: number) => void
): Promise<MediaUploadPart[]> {
  const parts = initResponse.presignedUrlParts!
  const uploadedParts: MediaUploadPart[] = []
  let totalUploaded = 0

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i]
    const start = i * CHUNK_SIZE
    const end = Math.min(start + CHUNK_SIZE, file.size)
    const chunk = file.slice(start, end)

    const eTag = await uploadPart(chunk, part.presignedUrl, (partProgress) => {
      const baseProgress = (i / parts.length) * 100
      const partContribution = (partProgress / 100) * (1 / parts.length) * 100
      onProgress(Math.round(baseProgress + partContribution))
    })

    uploadedParts.push({
      partNumber: part.partNumber,
      eTag
    })

    totalUploaded++
    onProgress(Math.round((totalUploaded / parts.length) * 100))
  }

  return uploadedParts
}

async function uploadPart(
  chunk: Blob,
  presignedUrl: string,
  onProgress: (progress: number) => void
): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const progress = Math.round((e.loaded / e.total) * 100)
        onProgress(progress)
      }
    })

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const eTag = xhr.getResponseHeader('ETag') || ''
        resolve(eTag.replace(/"/g, ''))
      } else {
        reject(new Error(`Part upload failed with status ${xhr.status}`))
      }
    })

    xhr.addEventListener('error', () => reject(new Error('Part upload failed')))

    xhr.open('PUT', presignedUrl)
    xhr.send(chunk)
  })
}
