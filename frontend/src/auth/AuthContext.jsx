/* eslint-disable react-refresh/only-export-components */
/**
 * Who is logged in.
 *   const { user, login, logout, setupAdmin } = useAuth()
 *
 * On page load a stored token is checked with GET /auth/me. If the server ever answers 401
 * (token expired, password changed, account disabled), the user is signed out and sent to the
 * login page with an explanation.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authApi, getToken, setToken, setUnauthorizedHandler } from '../services/api'

const AuthContext = createContext(null)
const SESSION_ENDED = 'Your session has expired or your account was changed. Please sign in again.'

export function AuthProvider({ children }) {
  // status: "checking" (validating a stored token) | "signed-in" | "signed-out"
  const [state, setState] = useState(() => ({ status: getToken() ? 'checking' : 'signed-out', user: null, notice: '' }))

  const logout = useCallback((notice = '') => {
    setToken(null)
    setState({ status: 'signed-out', user: null, notice })
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => logout(SESSION_ENDED))
  }, [logout])

  useEffect(() => {
    if (!getToken()) return undefined
    let cancelled = false
    authApi.me().then(
      (user) => !cancelled && setState({ status: 'signed-in', user, notice: '' }),
      // Keep the explanation when the server rejected the session (401), e.g. the account was disabled.
      (error) => !cancelled && logout(error?.response?.status === 401 ? SESSION_ENDED : ''),
    )
    return () => {
      cancelled = true
    }
  }, [logout])

  const acceptSession = useCallback((session) => {
    setToken(session.access_token)
    setState({ status: 'signed-in', user: session.user, notice: '' })
    return session.user
  }, [])

  const value = useMemo(
    () => ({
      ...state,
      isAdmin: state.user?.role === 'admin',
      login: async (email, password) => acceptSession(await authApi.login(email, password)),
      setupAdmin: async (fullName, email, password) => acceptSession(await authApi.setup(fullName, email, password)),
      logout,
      updateUser: (user) => setState((s) => ({ ...s, user })),
    }),
    [state, acceptSession, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
