import { MoreHorizontal, Search } from "lucide-react"
import { UserAvatar } from "./user-avatar"

// Sample content so the page looks like a live service. None of it comes from the API.
const TRENDS = [
  { category: "대한민국에서 트렌드 중", topic: "#백엔드", posts: "1.2만" },
  { category: "IT 인기 주제", topic: "PostgreSQL 18", posts: "4,281" },
  { category: "여행 트렌드", topic: "#제주한달살기", posts: "8,904" },
  { category: "AI 인기 주제", topic: "추천 시스템", posts: "2.3만" },
  { category: "스포츠 트렌드", topic: "#오운완", posts: "3.1만" },
]

const WHO_TO_FOLLOW = [
  { name: "백엔드 위클리", handle: "backend_weekly" },
  { name: "여행하는 개발자", handle: "travel_dev" },
  { name: "오늘의 운동", handle: "daily_workout" },
]

const FOOTER = ["이용약관", "개인정보 처리방침", "쿠키 정책", "접근성", "광고 정보", "더 보기"]

export function RightPanel() {
  return (
    <aside className="hidden w-[350px] shrink-0 pl-6 lg:block">
      <div className="sticky top-0 flex h-screen flex-col gap-4 overflow-y-auto pb-16 [scrollbar-width:none]">
        <div className="sticky top-0 z-10 bg-background pb-1 pt-1.5">
          <label className="flex h-[42px] items-center gap-3 rounded-full border border-transparent bg-[#202327] px-4 focus-within:border-primary focus-within:bg-background">
            <Search className="size-4 text-muted-foreground" />
            <input placeholder="검색" className="w-full bg-transparent text-[15px] outline-none placeholder:text-muted-foreground" />
          </label>
        </div>

        <Card title="프리미엄">
          <div className="px-4 pb-3">
            <p className="mb-3 leading-5">광고 없이 보고, 더 긴 글을 쓰고, 올린 글을 고칠 수 있어요.</p>
            <button type="button" className="h-9 rounded-full bg-primary px-4 font-bold text-white hover:bg-primary/90">
              구독하기
            </button>
          </div>
        </Card>

        <Card title="무슨 일이 일어나고 있나요?">
          {TRENDS.map((t) => (
            <Row key={t.topic}>
              <div className="flex-1">
                <p className="text-[13px] text-muted-foreground">{t.category}</p>
                <p className="font-bold">{t.topic}</p>
                <p className="text-[13px] text-muted-foreground">게시물 {t.posts}개</p>
              </div>
              <MoreHorizontal className="size-[18px] text-muted-foreground" />
            </Row>
          ))}
          <More />
        </Card>

        <Card title="팔로우 추천">
          {WHO_TO_FOLLOW.map((u) => (
            <Row key={u.handle}>
              <UserAvatar username={u.handle} />
              <div className="min-w-0 flex-1 leading-5">
                <p className="truncate font-bold">{u.name}</p>
                <p className="truncate text-muted-foreground">@{u.handle}</p>
              </div>
              <button type="button" className="h-8 rounded-full bg-secondary px-4 text-sm font-bold text-secondary-foreground hover:bg-secondary/90">
                팔로우
              </button>
            </Row>
          ))}
          <More />
        </Card>

        <nav className="flex flex-wrap gap-x-3 gap-y-1 px-4 text-[13px] text-muted-foreground">
          {FOOTER.map((item) => (
            <span key={item} className="cursor-pointer hover:underline">
              {item}
            </span>
          ))}
          <span>© 2026 SNS Corp.</span>
        </nav>
      </div>
    </aside>
  )
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="shrink-0 overflow-hidden rounded-2xl border border-border">
      <h2 className="px-4 py-3 text-xl font-extrabold">{title}</h2>
      {children}
    </section>
  )
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors hover:bg-foreground/[0.03]">{children}</div>
}

function More() {
  return <div className="cursor-pointer p-4 text-primary transition-colors hover:bg-foreground/[0.03]">더 보기</div>
}
