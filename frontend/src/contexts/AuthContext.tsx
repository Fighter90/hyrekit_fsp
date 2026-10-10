import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { GuestInput, RegisterInput, Role, User } from '../api/types'

interface AuthContextType {
  user: User | null
  role: Role | null
  isAuthenticated: boolean
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  /** Возвращает пользователя или null, если сервер попросил подтвердить почту без выдачи токенов. */
  register: (data: RegisterInput) => Promise<{ user: User | null; message: string | null }>
  /** Гостевой вход для экспресс-теста жюри */
  startGuest: (data: GuestInput) => Promise<User>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => !!api.getAccessToken())

  const logout = useCallback(() => {
    let rt: string | null = null
    try {
      rt = localStorage.getItem('refresh_token')
    } catch {
      /* storage недоступен */
    }
    if (rt) api.logout(rt).catch(() => {/* выход локально в любом случае */})
    api.clearTokens()
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    const me = await api.me()
    setUser(me)
  }, [])

  // Восстановление сессии при загрузке
  useEffect(() => {
    api.onSessionExpired = () => {
      api.clearTokens()
      setUser(null)
    }
    if (!api.getAccessToken()) return
    api.me()
      .then(setUser)
      .catch(() => api.clearTokens())
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.login(email, password)
    api.setTokens(tokens)
    const me = await api.me()
    setUser(me)
    return me
  }, [])

  const startGuest = useCallback(async (data: GuestInput) => {
    api.setTokens(await api.guest(data))
    const me = await api.me()
    setUser(me)
    return me
  }, [])

  const register = useCallback(async (data: RegisterInput) => {
    const res = await api.register(data)
    if (!('access_token' in res)) {
      return { user: null, message: res.message }
    }
    api.setTokens(res)
    const me = await api.me()
    setUser(me)
    return { user: me, message: null }
  }, [])

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      role: user?.role ?? null,
      isAuthenticated: !!user,
      loading,
      login,
      register,
      startGuest,
      logout,
      refreshUser,
    }),
    [user, loading, login, register, startGuest, logout, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
