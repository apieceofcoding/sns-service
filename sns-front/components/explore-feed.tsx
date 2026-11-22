"use client"

import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TweetCard } from "./tweet-card"
import type { Post } from "@/lib/types"

const originalPost1: Post = {
  id: 1001,
  userId: 101,
  username: "테크뉴스",
  userProfileMediaId: null,
  content: "최신 AI 기술이 우리의 일상을 어떻게 변화시키고 있는지 알아보세요. 혁신적인 변화가 시작되었습니다.",
  createdAt: new Date(Date.now() - 7200000).toISOString(), // 2시간 전
  modifiedAt: new Date(Date.now() - 7200000).toISOString(),
  likeCount: 234,
  repostCount: 89,
  replyCount: 45,
  viewCount: 5432,
  mediaIds: [],
  parentId: null,
  quoteId: null,
  repostId: null,
  isLikedByMe: false,
  likeIdByMe: null,
  isRepostedByMe: false,
  repostIdByMe: null,
}

const originalPost2: Post = {
  id: 1002,
  userId: 102,
  username: "개발자김씨",
  userProfileMediaId: null,
  content: "React 19가 드디어 릴리즈되었습니다! 새로운 기능들을 확인해보세요.",
  createdAt: new Date(Date.now() - 14400000).toISOString(), // 4시간 전
  modifiedAt: new Date(Date.now() - 14400000).toISOString(),
  likeCount: 567,
  repostCount: 234,
  replyCount: 89,
  viewCount: 12000,
  mediaIds: [],
  parentId: null,
  quoteId: null,
  repostId: null,
  isLikedByMe: true,
  likeIdByMe: 5001,
  isRepostedByMe: false,
  repostIdByMe: null,
}

const repostExample: Post = {
  id: 2001,
  userId: 103,
  username: "트렌드코리아",  // 재게시한 사람
  userProfileMediaId: null,
  content: "",  // 재게시는 본문 없음
  createdAt: new Date(Date.now() - 1800000).toISOString(), // 30분 전
  modifiedAt: new Date(Date.now() - 1800000).toISOString(),
  likeCount: 0,
  repostCount: 0,
  replyCount: 0,
  viewCount: 0,
  mediaIds: [],
  parentId: null,
  quoteId: null,
  repostId: 1001,  // 재게시한 원본 ID
  isLikedByMe: false,
  likeIdByMe: null,
  isRepostedByMe: false,
  repostIdByMe: null,
  repostedPost: originalPost1,
  repostedBy: {
    userId: 103,
    username: "트렌드코리아",
  },
}

const quoteExample: Post = {
  id: 3001,
  userId: 104,
  username: "스타트업맨",  // 인용한 사람
  userProfileMediaId: null,
  content: "이거 진짜 대박이네요! 우리 프로젝트에도 적용해봐야겠습니다. 특히 서버 컴포넌트 기능이 정말 기대됩니다.",  // 인용자의 코멘트
  createdAt: new Date(Date.now() - 3600000).toISOString(), // 1시간 전
  modifiedAt: new Date(Date.now() - 3600000).toISOString(),
  likeCount: 45,
  repostCount: 12,
  replyCount: 8,
  viewCount: 890,
  mediaIds: [],
  parentId: null,
  quoteId: 1002,  // 인용한 원본 ID
  repostId: null,
  isLikedByMe: false,
  likeIdByMe: null,
  isRepostedByMe: false,
  repostIdByMe: null,
  quotedPost: originalPost2,
}

const normalPost: Post = {
  id: 4001,
  userId: 105,
  username: "디자이너박",
  userProfileMediaId: null,
  content: "오늘 작업한 UI 디자인입니다. 피드백 부탁드려요! 다크모드와 라이트모드 모두 지원하도록 설계했습니다.",
  createdAt: new Date(Date.now() - 5400000).toISOString(), // 1.5시간 전
  modifiedAt: new Date(Date.now() - 5400000).toISOString(),
  likeCount: 123,
  repostCount: 34,
  replyCount: 56,
  viewCount: 2100,
  mediaIds: [],
  parentId: null,
  quoteId: null,
  repostId: null,
  isLikedByMe: true,
  likeIdByMe: 5002,
  isRepostedByMe: true,
  repostIdByMe: 6001,
}

const replyExample: Post = {
  id: 5001,
  userId: 106,
  username: "코딩초보",
  userProfileMediaId: null,
  content: "정말 유용한 정보네요! 저도 한번 시도해봐야겠어요.",
  createdAt: new Date(Date.now() - 900000).toISOString(), // 15분 전
  modifiedAt: new Date(Date.now() - 900000).toISOString(),
  likeCount: 5,
  repostCount: 0,
  replyCount: 1,
  viewCount: 120,
  mediaIds: [],
  parentId: 1001,  // 답글의 부모 게시물 ID
  quoteId: null,
  repostId: null,
  isLikedByMe: false,
  likeIdByMe: null,
  isRepostedByMe: false,
  repostIdByMe: null,
  parentPost: originalPost1,
}

const trendingPosts: Post[] = [
  repostExample,    // 재게시글
  quoteExample,     // 인용글
  normalPost,       // 일반 게시물
  replyExample,     // 답글
  originalPost2,    // 원본 게시물
]

export function ExploreFeed() {
  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="sticky top-0 z-10 bg-background/80 backdrop-blur-md border-b border-border p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input placeholder="검색" className="pl-12 bg-muted border-none rounded-full" />
        </div>
      </div>

      <Tabs defaultValue="trending" className="w-full">
        <TabsList className="w-full justify-start rounded-none border-b border-border bg-transparent h-auto p-0">
          <TabsTrigger
            value="trending"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-6 py-4"
          >
            트렌딩
          </TabsTrigger>
          <TabsTrigger
            value="latest"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-6 py-4"
          >
            최신
          </TabsTrigger>
          <TabsTrigger
            value="media"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-6 py-4"
          >
            미디어
          </TabsTrigger>
        </TabsList>

        <TabsContent value="trending" className="mt-0">
          {trendingPosts.map((post) => (
            <TweetCard key={post.id} post={post} />
          ))}
        </TabsContent>

        <TabsContent value="latest" className="mt-0">
          <div className="p-8 text-center text-muted-foreground">최신 트윗을 불러오는 중...</div>
        </TabsContent>

        <TabsContent value="media" className="mt-0">
          <div className="p-8 text-center text-muted-foreground">미디어 콘텐츠를 불러오는 중...</div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
