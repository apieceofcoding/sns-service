import { Button } from "@/components/ui/button"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"

const relatedPeople = [
  { name: "김개발", username: "devkim", bio: "프론트엔드 개발자 | React, TypeScript" },
  { name: "이디자인", username: "designlee", bio: "UI/UX 디자이너 | Figma 마스터" },
  { name: "박테크", username: "techpark", bio: "풀스택 개발자 | 스타트업 CTO" },
]

const happeningNow = [
  { category: "트렌드", title: "#연말정산", description: "직장인들의 필수 체크리스트", posts: "12.5K" },
  { category: "엔터테인먼트", title: "#신작드라마", description: "화제의 새 드라마 첫 방송", posts: "45.2K" },
  { category: "기술", title: "#AI트렌드2024", description: "인공지능 최신 동향", posts: "8.9K" },
]

export function PostDetailSidebar() {
  return (
    <div className="p-4 space-y-4">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <Input placeholder="검색" className="pl-12 bg-muted border-none rounded-full" />
      </div>

      <Card className="overflow-hidden">
        <div className="p-4">
          <h2 className="text-xl font-bold">연관된 사람</h2>
        </div>
        {relatedPeople.map((person, index) => (
          <div
            key={index}
            className="p-4 flex items-center justify-between hover:bg-accent/50 transition-colors cursor-pointer border-t border-border"
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center text-white font-bold">
                {person.name.charAt(0)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-bold truncate">{person.name}</div>
                <div className="text-sm text-muted-foreground">@{person.username}</div>
                <div className="text-sm text-muted-foreground truncate">{person.bio}</div>
              </div>
            </div>
            <Button variant="outline" size="sm" className="rounded-full font-bold bg-transparent flex-shrink-0 ml-2">
              팔로우
            </Button>
          </div>
        ))}
        <div className="p-4 text-primary hover:bg-accent/50 transition-colors cursor-pointer border-t border-border">
          더 보기
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="p-4">
          <h2 className="text-xl font-bold">무슨 일이 일어나고 있나요?</h2>
        </div>
        {happeningNow.map((item, index) => (
          <div
            key={index}
            className="p-4 hover:bg-accent/50 transition-colors cursor-pointer border-t border-border"
          >
            <div className="text-sm text-muted-foreground">{item.category}</div>
            <div className="font-bold">{item.title}</div>
            <div className="text-sm text-muted-foreground">{item.description}</div>
            <div className="text-sm text-muted-foreground mt-1">{item.posts}개의 게시물</div>
          </div>
        ))}
        <div className="p-4 text-primary hover:bg-accent/50 transition-colors cursor-pointer border-t border-border">
          더 보기
        </div>
      </Card>
    </div>
  )
}
