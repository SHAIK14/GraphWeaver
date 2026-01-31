"use client";

import React from "react";
import Link from "next/link";
import Logo from "@/components/layout/Logo";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#fcfaf7] text-[#212121] flex flex-col">
      <header className="border-b border-[#e0e0e0]/80 bg-[#fcfaf7] sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-8 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <Logo className="w-8 h-8" />
            <span className="text-[14px] font-semibold tracking-tight uppercase text-zinc-900 font-mono">
              GraphWeaver
            </span>
          </Link>
          <Link
            href="/login"
            className="text-[13px] font-medium text-zinc-500 hover:text-[#212121] transition-colors"
          >
            Log in
          </Link>
        </div>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-8 py-24">
        <div className="max-w-2xl mx-auto text-center">
          <p className="gw-section-header mb-5">Knowledge Engineering</p>
          <h1 className="gw-page-title font-normal tracking-tight text-[#212121] mb-5 leading-tight">
            Build and query your knowledge graph in one place.
          </h1>
          <p className="text-[16px] text-zinc-500 leading-relaxed mb-14 max-w-lg mx-auto">
            Define your goal, select data, approve schema, then build and query. Secure and built for complex reasoning.
          </p>
          <Link
            href="/signup"
            className="inline-block px-10 py-3.5 bg-[#212121] text-white text-[14px] font-medium rounded-lg hover:bg-black transition-colors"
          >
            Start building
          </Link>
        </div>

        <div className="mt-28 max-w-2xl mx-auto grid grid-cols-1 sm:grid-cols-3 gap-10 text-center">
          <div className="text-zinc-500">
            <p className="text-[11px] font-mono uppercase tracking-wider text-[#39594d] mb-2">Define</p>
            <p className="text-[14px]">Set your graph goal in plain language.</p>
          </div>
          <div className="text-zinc-500">
            <p className="text-[11px] font-mono uppercase tracking-wider text-[#39594d] mb-2">Build</p>
            <p className="text-[14px]">Approve schema, then one-click build.</p>
          </div>
          <div className="text-zinc-500">
            <p className="text-[11px] font-mono uppercase tracking-wider text-[#39594d] mb-2">Query</p>
            <p className="text-[14px]">Ask questions with GraphRAG.</p>
          </div>
        </div>
      </main>

      <footer className="border-t border-[#e0e0e0]/60 py-5 px-8">
        <div className="max-w-6xl mx-auto flex justify-between text-[11px] font-mono uppercase tracking-wider text-zinc-400">
          <span>GraphWeaver</span>
          <span>© 2026</span>
        </div>
      </footer>
    </div>
  );
}
