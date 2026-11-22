"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { X, ChevronLeft, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

interface ImageLightboxProps {
  images: { id: number; url: string }[]
  initialIndex: number
  onClose: () => void
}

export function ImageLightbox({ images, initialIndex, onClose }: ImageLightboxProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex)
  const [isAnimating, setIsAnimating] = useState(false)
  const [dragOffset, setDragOffset] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const startXRef = useRef(0)
  const startYRef = useRef(0)

  const currentImage = images[currentIndex]
  const hasMultiple = images.length > 1
  const hasPrev = currentIndex > 0
  const hasNext = currentIndex < images.length - 1

  const goToPrev = useCallback(() => {
    if (hasPrev && !isAnimating) {
      setIsAnimating(true)
      setCurrentIndex(prev => prev - 1)
      setTimeout(() => setIsAnimating(false), 300)
    }
  }, [hasPrev, isAnimating])

  const goToNext = useCallback(() => {
    if (hasNext && !isAnimating) {
      setIsAnimating(true)
      setCurrentIndex(prev => prev + 1)
      setTimeout(() => setIsAnimating(false), 300)
    }
  }, [hasNext, isAnimating])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case "Escape":
          onClose()
          break
        case "ArrowLeft":
          goToPrev()
          break
        case "ArrowRight":
          goToNext()
          break
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [onClose, goToPrev, goToNext])

  useEffect(() => {
    const originalStyle = window.getComputedStyle(document.body).overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = originalStyle
    }
  }, [])

  const handleDragStart = (clientX: number, clientY: number) => {
    setIsDragging(true)
    startXRef.current = clientX
    startYRef.current = clientY
  }

  const handleDragMove = (clientX: number) => {
    if (!isDragging) return
    const diff = clientX - startXRef.current
    setDragOffset(diff)
  }

  const handleDragEnd = () => {
    if (!isDragging) return
    setIsDragging(false)

    const threshold = 100
    if (dragOffset > threshold && hasPrev) {
      goToPrev()
    } else if (dragOffset < -threshold && hasNext) {
      goToNext()
    }
    setDragOffset(0)
  }

  const handleTouchStart = (e: React.TouchEvent) => {
    handleDragStart(e.touches[0].clientX, e.touches[0].clientY)
  }

  const handleTouchMove = (e: React.TouchEvent) => {
    handleDragMove(e.touches[0].clientX)
  }

  const handleTouchEnd = () => {
    handleDragEnd()
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    handleDragStart(e.clientX, e.clientY)
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    handleDragMove(e.clientX)
  }

  const handleMouseUp = () => {
    handleDragEnd()
  }

  const handleMouseLeave = () => {
    if (isDragging) {
      handleDragEnd()
    }
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
      onClick={handleBackdropClick}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    >
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between p-4 z-10">
        <button
          onClick={onClose}
          className="p-2 rounded-full bg-black/50 hover:bg-black/70 transition-colors"
        >
          <X className="w-6 h-6 text-white" />
        </button>

        {hasMultiple && (
          <div className="text-white text-sm font-medium bg-black/50 px-3 py-1.5 rounded-full">
            {currentIndex + 1} / {images.length}
          </div>
        )}

        <div className="w-10" />
      </div>

      {hasMultiple && hasPrev && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            goToPrev()
          }}
          className="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/50 hover:bg-black/70 transition-colors z-10"
        >
          <ChevronLeft className="w-8 h-8 text-white" />
        </button>
      )}

      {hasMultiple && hasNext && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            goToNext()
          }}
          className="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/50 hover:bg-black/70 transition-colors z-10"
        >
          <ChevronRight className="w-8 h-8 text-white" />
        </button>
      )}

      <div
        className="w-full h-full flex items-center justify-center p-16 select-none"
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onMouseDown={handleMouseDown}
      >
        <div
          className={cn(
            "relative max-w-full max-h-full transition-transform duration-300 ease-out",
            isDragging && "transition-none"
          )}
          style={{
            transform: `translateX(${dragOffset}px)`,
          }}
        >
          <img
            src={currentImage.url}
            alt=""
            className="max-w-full max-h-[calc(100vh-8rem)] object-contain pointer-events-none"
            draggable={false}
          />
        </div>
      </div>

      {hasMultiple && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex gap-2">
          {images.map((_, index) => (
            <button
              key={index}
              onClick={(e) => {
                e.stopPropagation()
                setCurrentIndex(index)
              }}
              className={cn(
                "w-2 h-2 rounded-full transition-all",
                index === currentIndex
                  ? "bg-white w-4"
                  : "bg-white/50 hover:bg-white/70"
              )}
            />
          ))}
        </div>
      )}
    </div>
  )
}
