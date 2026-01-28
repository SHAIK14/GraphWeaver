"use client";

import React from 'react';
import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-black text-white font-sans flex flex-col items-center justify-center p-8">
      <div className="max-w-4xl w-full">
        <header className="mb-24">
          <div className="flex items-center gap-3 mb-10">
            <div className="w-12 h-12 bg-white flex items-center justify-center text-black font-black text-xl">G</div>
            <h1 className="text-2xl font-black tracking-tighter uppercase">GraphWeaver</h1>
          </div>
          <h2 className="text-6xl lg:text-8xl font-black tracking-tighter leading-[0.9] uppercase mb-12">
            State-of-the-art<br />
            Knowledge<br />
            Engineering.
          </h2>
          <p className="text-xl text-zinc-500 max-w-2xl font-medium leading-relaxed">
            The foundation for your enterprise knowledge graph. Secure, private, and built for complex reasoning.
          </p>
        </header>

        <Link href="/chat" className="group p-10 border border-zinc-800 bg-zinc-900/20 hover:bg-white hover:text-black transition-all duration-300 block">
          <div className="flex justify-between items-start mb-12">
            <span className="text-xs font-black tracking-widest uppercase opacity-50">Unified_Interface</span>
            <span className="text-2xl">→</span>
          </div>
          <h3 className="text-4xl font-black tracking-tight uppercase mb-4">Start Building</h3>
          <p className="text-sm opacity-60 font-medium">Build your knowledge graph and query it - all in one conversational interface.</p>
        </Link>

        <footer className="mt-32 border-t border-zinc-900 pt-12 flex justify-between text-[10px] font-black uppercase tracking-[0.4em] text-zinc-700">
          <span>GraphWeaver // v1.0.4</span>
          <span>© 2026 Systems Corp</span>
        </footer>
      </div>
    </div>
  );
}
