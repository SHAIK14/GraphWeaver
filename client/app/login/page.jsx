"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Logo from "@/components/layout/Logo";
import { signIn } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await signIn(email, password);
      router.push("/chat");
    } catch (err) {
      setError(err.message || "Login failed");
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
          <h1 className="text-[26px] font-normal tracking-tight text-[#212121] mb-10">
            Welcome back
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
                className="w-full px-4 py-3 border border-[#e0e0e0] rounded-lg text-[15px] text-[#212121] placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-[#39594d]/20 focus:border-[#39594d] transition-colors"
                placeholder="••••••••"
              />
            </label>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 bg-[#39594d] text-white text-[14px] font-medium rounded-lg hover:bg-[#2d4439] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? "Signing in…" : "Log in"}
            </button>
          </form>

          <p className="mt-8 text-center text-[13px] text-zinc-500">
            Don’t have an account?{" "}
            <Link href="/signup" className="text-[#39594d] font-medium hover:underline">
              Sign up
            </Link>
          </p>
        </div>
      </main>
    </div>
  );
}
