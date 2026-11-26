export interface CreateLinkRequest {
  original_url: string
}

export interface ShortLink {
  id: string
  original_url: string
  short_code: string
  short_url: string
  is_active: true
  created_at: string
  expires_at: null
}

export type ShortenerState =
  | { status: 'idle' | 'validating' | 'submitting' }
  | { status: 'success'; link: ShortLink }
  | { status: 'error'; message: string }
