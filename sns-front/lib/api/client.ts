import { ApiError } from '@/lib/types'

export class ApiClient {
  private baseURL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080'

  async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseURL}${endpoint}`

    const response = await fetch(url, {
      ...options,
      credentials: 'include', // 쿠키 기반 세션을 위해 필요
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (response.status === 401) {
      const isAuthEndpoint = endpoint === '/api/v1/users/me'
      if (isAuthEndpoint && typeof window !== 'undefined') {
        const currentPath = window.location.pathname
        if (currentPath !== '/login' && currentPath !== '/signup') {
          window.location.href = '/login'
        }
      }
      throw new ApiError(401, 'Unauthorized')
    }

    if (response.status === 204) {
      return undefined as T
    }

    if (!response.ok) {
      let errorMessage = 'Request failed'
      let errorDetails = undefined

      try {
        const errorData = await response.json()
        errorMessage = errorData.message || errorMessage
        errorDetails = errorData
      } catch {
      }

      throw new ApiError(response.status, errorMessage, errorDetails)
    }

    const text = await response.text()
    if (!text) {
      return undefined as T
    }
    try {
      return JSON.parse(text)
    } catch {
      return undefined as T
    }
  }

  async get<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'GET',
    })
  }

  async post<T>(
    endpoint: string,
    data?: unknown,
    options?: RequestInit
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async postForm<T>(
    endpoint: string,
    data: URLSearchParams,
    options?: RequestInit
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        ...options?.headers,
      },
      body: data.toString(),
    })
  }

  async put<T>(
    endpoint: string,
    data?: unknown,
    options?: RequestInit
  ): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.request<T>(endpoint, {
      ...options,
      method: 'DELETE',
    })
  }
}

export const apiClient = new ApiClient()
