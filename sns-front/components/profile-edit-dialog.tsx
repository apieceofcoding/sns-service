"use client"

import { useState, useRef } from "react"
import { Camera, X, Loader2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { useAuth } from "@/hooks/api/use-auth"
import { useProfileImageUpload } from "@/hooks/api/use-profile"

interface ProfileEditDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ProfileEditDialog({ open, onOpenChange }: ProfileEditDialogProps) {
  const { user } = useAuth()
  const { uploadProfileImage, isUploading, progress } = useProfileImageUpload()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.type.startsWith('image/')) {
      return
    }

    setSelectedFile(file)
    const preview = URL.createObjectURL(file)
    setPreviewUrl(preview)
  }

  const handleSave = async () => {
    if (!selectedFile) return

    const success = await uploadProfileImage(selectedFile)
    if (success) {
      handleClose()
    }
  }

  const handleClose = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
    }
    setPreviewUrl(null)
    setSelectedFile(null)
    onOpenChange(false)
  }

  const handleRemovePreview = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
    }
    setPreviewUrl(null)
    setSelectedFile(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const currentImageUrl = previewUrl || user?.profileImageUrl

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>프로필 수정</DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="flex flex-col items-center gap-4">
            <div className="relative">
              <div className="w-32 h-32 rounded-full overflow-hidden bg-muted border-4 border-background">
                {currentImageUrl ? (
                  <img
                    src={currentImageUrl}
                    alt="프로필"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-4xl text-muted-foreground font-medium">
                    {user?.username?.charAt(0).toUpperCase() || '?'}
                  </div>
                )}
              </div>

              <button
                onClick={() => fileInputRef.current?.click()}
                className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity"
                disabled={isUploading}
              >
                <Camera className="w-8 h-8 text-white" />
              </button>

              {previewUrl && (
                <button
                  onClick={handleRemovePreview}
                  className="absolute -top-1 -right-1 w-6 h-6 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center"
                  disabled={isUploading}
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />

            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              이미지 선택
            </Button>
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium text-muted-foreground">사용자명</div>
            <div className="text-lg font-semibold">{user?.username}</div>
          </div>

          {isUploading && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                업로드 중...
              </div>
              <Progress value={progress} className="h-2" />
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={handleClose} disabled={isUploading}>
            취소
          </Button>
          <Button
            onClick={handleSave}
            disabled={!selectedFile || isUploading}
          >
            {isUploading ? "저장 중..." : "저장"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
