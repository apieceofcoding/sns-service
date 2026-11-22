'use client'

import { createContext, useContext, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { usersApi } from '@/lib/api/users'
import type { User } from '@/lib/types'

interface AuthContextType {
  user: User | null | undefined
  isLoading: boolean
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data: user, isLoading, isError } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => usersApi.getMe(),
    retry: false,
    staleTime: 5 * 60 * 1000, // 5분
  })

  const isValidUser = !!user && typeof user.id === 'number' && typeof user.username === 'string'

  const value: AuthContextType = {
    user: isValidUser ? user : null,
    isLoading,
    isAuthenticated: !isError && isValidUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuthContext() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuthContext must be used within AuthProvider')
  }
  return context
}
