export interface Quote {
  id: number
  content: string
  userId: number
  username: string
  quoteId: number
  createdAt: string
  modifiedAt: string
}

export interface QuoteCreateRequest {
  content: string
}
