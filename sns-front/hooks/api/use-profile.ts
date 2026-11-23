'use client'

import { useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { profileApi } from '@/lib/api/profile'

export function useMyLikes(enabled: boolean = true) {
  return useQuery({
    queryKey: ['profile', 'likes'],
    queryFn: () => profileApi.getMyLikes(),
    enabled,
    retry: false,
  })
}

export function useProfileImageUpload() {
  const queryClient = useQueryClient()
  const [isUploading, setIsUploading] = useState(false)
  const [progress, setProgress] = useState(0)

  const uploadProfileImage = useCallback(async (file: File): Promise<boolean> => {
    setIsUploading(true)
    setProgress(0)

    try {
      const initResponse = await profileApi.initProfileImage({
        fileSize: file.size
      })

      setProgress(20)

      if (initResponse.presignedUrl) {
        await uploadToS3(file, initResponse.presignedUrl, (p) => {
          setProgress(20 + Math.round(p * 0.6))
        })
      }

      setProgress(85)

      await profileApi.uploadedProfileImage(initResponse.id)

      setProgress(100)

      await queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })

      toast.success('프로필 이미지가 업데이트되었습니다!')
      return true
    } catch {
      toast.error('프로필 이미지 업로드 실패')
      return false
    } finally {
      setIsUploading(false)
      setProgress(0)
    }
  }, [queryClient])

  return {
    uploadProfileImage,
    isUploading,
    progress
  }
}

async function uploadToS3(
  file: File,
  presignedUrl: string,
  onProgress: (progress: number) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        onProgress(e.loaded / e.total)
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
