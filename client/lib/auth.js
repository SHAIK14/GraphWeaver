import { supabase } from './supabase'

/**
 * Sign up with email and password
 */
export async function signUp(email, password) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
  })

  if (error) throw error
  return data
}

/**
 * Sign in with email and password
 */
export async function signIn(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  })

  if (error) throw error
  return data
}

/**
 * Sign out
 */
export async function signOut() {
  const { error } = await supabase.auth.signOut()
  if (error) throw error
}

/**
 * Get current session
 */
export async function getSession() {
  const { data: { session }, error } = await supabase.auth.getSession()
  if (error) throw error
  return session
}

/**
 * Get current user
 */
export async function getUser() {
  const { data: { user }, error } = await supabase.auth.getUser()
  if (error) throw error
  return user
}

/**
 * Get JWT access token (triggers auto-refresh if needed)
 */
export async function getAccessToken() {
  // getUser() triggers token refresh if expired
  const user = await getUser()
  if (!user) return null

  // Now get the refreshed session
  const session = await getSession()
  return session?.access_token || null
}
