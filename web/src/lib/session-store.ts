import type { StoredSession } from './api/types'

export const SESSION_STORAGE_KEY = 'researchswarm:session'

const memory = new Map<string, string>()

function randomUuid(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export function isStoragePersistent(): boolean {
  try {
    const k = '__rs_probe__'
    localStorage.setItem(k, '1')
    localStorage.removeItem(k)
    return true
  } catch {
    return false
  }
}

export class SessionStore {
  private useMemory = false

  constructor() {
    this.useMemory = !isStoragePersistent()
  }

  get(): StoredSession | null {
    let raw: string | null = null
    try {
      raw = this.useMemory ? memory.get(SESSION_STORAGE_KEY) ?? null : localStorage.getItem(SESSION_STORAGE_KEY)
    } catch {
      this.useMemory = true
      raw = memory.get(SESSION_STORAGE_KEY) ?? null
    }
    if (!raw) return null
    try {
      const o = JSON.parse(raw) as Record<string, unknown>
      return {
        sessionId: String(o.sessionId ?? ''),
        principalId: String(o.principalId ?? ''),
        createdAt: String(o.createdAt ?? ''),
        expiresAt: String(o.expiresAt ?? ''),
      }
    } catch {
      return null
    }
  }

  /** Returns existing principalId or creates and persists one. */
  ensurePrincipalId(): string {
    const existing = this.get()
    if (existing?.principalId) return existing.principalId
    const principalId = randomUuid()
    const payload: StoredSession = {
      sessionId: existing?.sessionId ?? '',
      principalId,
      createdAt: existing?.createdAt ?? new Date().toISOString(),
      expiresAt: existing?.expiresAt ?? '',
    }
    if (!payload.createdAt) payload.createdAt = new Date().toISOString()
    this.set(payload)
    return principalId
  }

  set(session: StoredSession): void {
    const raw = JSON.stringify(session)
    try {
      if (this.useMemory) {
        memory.set(SESSION_STORAGE_KEY, raw)
      } else {
        localStorage.setItem(SESSION_STORAGE_KEY, raw)
      }
    } catch {
      this.useMemory = true
      memory.set(SESSION_STORAGE_KEY, raw)
    }
  }

  clear(): void {
    try {
      if (this.useMemory) {
        memory.delete(SESSION_STORAGE_KEY)
      } else {
        localStorage.removeItem(SESSION_STORAGE_KEY)
      }
    } catch {
      this.useMemory = true
      memory.delete(SESSION_STORAGE_KEY)
    }
  }

  /** Clear server session fields; keep principalId for Bearer token. */
  clearServerSession(): void {
    const cur = this.get()
    if (!cur?.principalId) return
    this.set({
      principalId: cur.principalId,
      createdAt: cur.createdAt || new Date().toISOString(),
      sessionId: '',
      expiresAt: '',
    })
  }
}

export const sessionStore = new SessionStore()
