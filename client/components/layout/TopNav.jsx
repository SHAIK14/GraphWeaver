"use client";

import React from 'react';
import Link from 'next/link';

const TopNav = () => {
  return (
    <nav className="h-[64px] border-b border-[#e0e0e0] bg-white flex items-center justify-between px-12 fixed top-0 right-0 left-[240px] z-40 backdrop-blur-md bg-white/70">
      <div className="flex items-center gap-8">
        {/* Placeholder for Breadcrumbs or Page Category */}
        <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-[0.2em]">Dashboard</span>
      </div>

      <div className="flex items-center gap-10">
        <div className="hidden md:flex items-center gap-8 text-[13px] font-medium text-zinc-500 tracking-tight">
          <Link href="/dashboard" className="text-black font-bold">Dashboard</Link>
          <Link href="#" className="hover:text-black transition-colors">Playground</Link>
          <Link href="#" className="hover:text-black transition-colors">Docs</Link>
          <Link href="#" className="hover:text-black transition-colors">Community</Link>
        </div>
        <div className="w-px h-6 bg-zinc-200"></div>
        <button className="text-zinc-600 hover:text-black transition-colors relative">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <div className="absolute -top-1 -right-1 w-2 h-2 bg-[#ff7759] rounded-full border border-white"></div>
        </button>
      </div>
    </nav>
  );
};

export default TopNav;
