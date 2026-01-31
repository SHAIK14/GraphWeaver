"use client";

import { createContext, useContext, useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { supabase } from './supabase';

const AuthContext = createContext({});

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Get initial session
    const initAuth = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        console.log('[AuthContext] Initial session:', session?.user?.email || 'No user');
        setUser(session?.user ?? null);
      } catch (error) {
        console.error('[AuthContext] Init error:', error);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    initAuth();

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        console.log('[AuthContext] Auth event:', event, 'User:', session?.user?.email || 'No user');

        setUser(session?.user ?? null);
        setLoading(false);

        // Handle different auth events
        if (event === 'SIGNED_IN') {
          // User signed in - redirect to chat
          console.log('[AuthContext] User signed in, redirecting to /chat');
          router.push('/chat');
        } else if (event === 'SIGNED_OUT') {
          // User signed out - redirect to login
          console.log('[AuthContext] User signed out, redirecting to /login');
          router.push('/login');
        } else if (event === 'TOKEN_REFRESHED') {
          console.log('[AuthContext] Token refreshed');
        } else if (event === 'USER_UPDATED') {
          console.log('[AuthContext] User updated');
        }
      }
    );

    return () => {
      subscription.unsubscribe();
    };
  }, [router]);

  // Protect routes
  useEffect(() => {
    if (loading) {
      console.log('[AuthContext] Still loading...');
      return;
    }

    const publicRoutes = ['/', '/login', '/signup'];
    const isPublicRoute = publicRoutes.includes(pathname);

    console.log('[AuthContext] Route protection:', {
      pathname,
      user: user?.email || 'No user',
      isPublicRoute,
      loading
    });

    if (!user && !isPublicRoute) {
      // Not authenticated, redirect to login
      console.log('[AuthContext] Not authenticated, redirecting to /login');
      router.push('/login');
    } else if (user && (pathname === '/login' || pathname === '/signup')) {
      // Already authenticated and on auth pages, redirect to chat
      console.log('[AuthContext] Already authenticated, redirecting to /chat');
      router.push('/chat');
    }
  }, [user, loading, pathname, router]);

  const value = {
    user,
    loading,
    signOut: async () => {
      console.log('[AuthContext] Signing out...');
      await supabase.auth.signOut();
    }
  };

  // Show loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-[#fcfaf7] flex items-center justify-center">
        <div className="text-zinc-500 text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
