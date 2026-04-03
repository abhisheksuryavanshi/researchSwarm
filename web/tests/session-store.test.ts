import { describe, expect, it } from 'vitest'
import { SessionStore } from '../src/lib/session-store'

describe('SessionStore', () => {
  it('returns stable principalId from ensurePrincipalId', () => {
    const s = new SessionStore()
    const a = s.ensurePrincipalId()
    const b = s.ensurePrincipalId()
    expect(a).toBe(b)
    expect(a.length).toBeGreaterThan(30)
  })
})
