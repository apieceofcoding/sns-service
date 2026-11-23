"use client"

import { useEffect, useRef, useState } from "react"
import { Loader2 } from "lucide-react"
import { TweetComposer } from "./tweet-composer"
import { TweetCard } from "./tweet-card"
import { useTimeline } from "@/hooks/api/use-timeline"
import type { Feed } from "@/lib/api/timeline"
import { cn } from "@/lib/utils"

const TABS: { value: Feed; label: string }[] = [
  { value: "recommend", label: "추천" },
  { value: "timelines", label: "팔로잉" },
]

export function HomeFeed() {
  const [feed, setFeed] = useState<Feed>("timelines")
  const { data, isLoading, error, fetchNextPage, hasNextPage, isFetchingNextPage } = useTimeline(20, feed)
  const loadMoreRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = loadMoreRef.current
    if (!element) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) fetchNextPage()
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [fetchNextPage, hasNextPage, isFetchingNextPage])

  const posts = data?.pages.flatMap((page) => page.posts) ?? []

  return (
    <>
      <div role="tablist" aria-label="피드 선택" className="sticky top-0 z-10 flex h-[53px] border-b border-border bg-background/65 backdrop-blur-md">
        {TABS.map(({ value, label }) => {
          const active = feed === value
          return (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setFeed(value)}
              className="flex flex-1 justify-center transition-colors hover:bg-foreground/10"
            >
              <span className={cn("relative flex items-center", active ? "font-bold" : "font-medium text-muted-foreground")}>
                {label}
                {active && <span className="absolute inset-x-0 bottom-0 h-1 rounded-full bg-primary" />}
              </span>
            </button>
          )
        })}
      </div>

      <TweetComposer />

      {isLoading && <Spinner />}
      {error && <Message>피드를 불러올 수 없습니다.</Message>}
      {!isLoading && !error && posts.length === 0 && (
        <Message>{feed === "recommend" ? "아직 준비된 추천 게시물이 없습니다." : "아직 게시물이 없습니다."}</Message>
      )}

      {posts.map((post) => (
        <TweetCard key={post.id} post={post} />
      ))}

      <div ref={loadMoreRef} className="h-10">
        {isFetchingNextPage && <Spinner />}
      </div>
    </>
  )
}

function Spinner() {
  return (
    <div className="flex justify-center p-6">
      <Loader2 className="size-6 animate-spin text-primary" />
    </div>
  )
}

function Message({ children }: { children: React.ReactNode }) {
  return <p className="p-8 text-center text-muted-foreground">{children}</p>
}
