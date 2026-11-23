"use client"

import { use } from "react"
import { FollowList } from "@/components/follow-list"

export default function Page({ params }: { params: Promise<{ userId: string }> }) {
  return <FollowList userId={parseInt(use(params).userId, 10)} kind="following" />
}
