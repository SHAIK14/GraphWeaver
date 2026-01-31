"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Logo from "@/components/layout/Logo";
import { signUp } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const { data } = await signUp(email, password);

      console.log('Signup response:', data);

      // Check if email confirmation is required
      // Supabase returns user but session might be null or user.email_confirmed_at is null
      if (data?.user) {
        if (!data.user.email_confirmed_at) {
          // Email confirmation required
          setSuccess(true);
        } else if (data.session) {
          // Auto-logged in (email confirmation disabled)
          router.push("/chat");
        } else {
          // Edge case: user exists but no session
          setSuccess(true);
        }
      }
    } catch (err) {
      setError(err.message || "Sign up failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#fcfaf7] text-[#212121] flex flex-col">
      <header className="border-b border-[#e0e0e0]/80 bg-[#fcfaf7]">
        <div className="max-w-6xl mx-auto px-8 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <Logo className="w-8 h-8" />
            <span className="text-[14px] font-semibold tracking-tight uppercase text-zinc-900 font-mono">
              GraphWeaver
            </span>
          </Link>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-8 py-20">
        <div className="w-full max-w-[380px]">
          {!success ? (
            <>
              <h1 className="text-[26px] font-normal tracking-tight text-[#212121] mb-10">
                Create your account
              </h1>

              <form onSubmit={handleSubmit} className="gw-card p-8">
                {error && (
                  <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[13px] font-medium">
                    {error}
                  </div>
                )}
                <label className="block mb-4">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-2 block">
                    Email
                  </span>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full px-4 py-3 border border-[#e0e0e0] rounded-lg text-[15px] text-[#212121] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-[#39594d]/20 focus:border-[#39594d] transition-colors"
                    placeholder="you@example.com"
                  />
                </label>
                <label className="block mb-6">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-2 block">
                    Password
                  </span>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                    className="w-full px-4 py-3 border border-[#e0e0e0] rounded-lg text-[15px] text-[#212121] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-[#39594d]/20 focus:border-[#39594d] transition-colors"
                    placeholder="••••••••"
                  />
                </label>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3.5 bg-[#39594d] text-white text-[14px] font-medium rounded-lg hover:bg-[#2d4439] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {loading ? "Creating account…" : "Sign up"}
                </button>
              </form>

              <p className="mt-8 text-center text-[13px] text-zinc-500">
                Already have an account?{" "}
                <Link href="/login" className="text-[#39594d] font-medium hover:underline">
                  Log in
                </Link>
              </p>
            </>
          ) : (
            <div className="gw-card p-8 text-center">
              <div className="w-12 h-12 bg-[#e8f4f0] rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-[#39594d]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <h2 className="text-[20px] font-normal tracking-tight text-[#212121] mb-3">
                Check your email
              </h2>
              <p className="text-[14px] text-zinc-600 mb-2">
                We sent a confirmation link to
              </p>
              <p className="text-[14px] font-medium text-[#212121] mb-6">
                {email}
              </p>
              <p className="text-[13px] text-zinc-500 mb-6">
                Click the link in the email to confirm your account and get started.
              </p>
              <Link
                href="/login"
                className="inline-block text-[13px] text-[#39594d] font-medium hover:underline"
              >
                Back to login
              </Link>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
