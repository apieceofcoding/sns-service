"use client"

import { useState } from "react"
import { toast } from "sonner"
import { useAuth } from "@/hooks/api/use-auth"
import { AuthField, AuthForm } from "@/components/auth-form"

export default function SignupPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const { signup, isSignupPending } = useAuth()

  const submit = () => {
    if (password !== confirm) return toast.error("비밀번호가 일치하지 않습니다")
    if (password.length < 4) return toast.error("비밀번호는 4자 이상이어야 합니다")
    signup({ username, password })
  }

  return (
    <AuthForm
      title="계정을 생성하세요"
      submitLabel="가입하기"
      pending={isSignupPending}
      onSubmit={submit}
      footer={{ text: "이미 계정이 있으신가요?", link: "로그인하기", href: "/login" }}
    >
      <AuthField label="사용자 이름" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
      <AuthField label="비밀번호" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <AuthField label="비밀번호 확인" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
    </AuthForm>
  )
}
