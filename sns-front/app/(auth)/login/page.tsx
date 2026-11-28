"use client"

import { useState } from "react"
import { useAuth } from "@/hooks/api/use-auth"
import { AuthField, AuthForm } from "@/components/auth-form"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const { login, isLoginPending } = useAuth()

  return (
    <AuthForm
      title="로그인하기"
      submitLabel="로그인"
      pending={isLoginPending}
      onSubmit={() => login({ username, password })}
      footer={{ text: "계정이 없으신가요?", link: "가입하기", href: "/signup" }}
    >
      <AuthField label="사용자 이름" name="username" type="text" autoComplete="off" autoCapitalize="none" spellCheck={false} value={username} onChange={(e) => setUsername(e.target.value)} />
      <AuthField label="비밀번호" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
    </AuthForm>
  )
}
