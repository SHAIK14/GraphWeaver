"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import Logo from './Logo';
import { useAuth } from '@/lib/AuthContext';

const Sidebar = () => {
  const pathname = usePathname();
  const { signOut } = useAuth();

  const navGroups = [
    {
      label: "WORKSPACE",
      items: [
        { label: "New Session", href: "/chat" },
      ]
    },
    {
      label: "SETTINGS",
      items: [
        { label: "API Keys", href: "#" },
        { label: "Usage", href: "#" },
      ]
    }
  ];

  const handleLogout = async () => {
    try {
      await signOut();
      // AuthContext handles redirect to /login
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <aside className="w-[240px] h-screen bg-[#fafafa] border-r border-[#e0e0e0] flex flex-col pt-12 fixed left-0 top-0 z-50">
      <div className="mb-12 px-8 flex items-center gap-3">
        <Logo className="w-8 h-8" />
        <span className="text-[14px] font-bold tracking-tighter uppercase text-zinc-900 font-mono">GraphWeaver</span>
      </div>

      <nav className="flex-1 overflow-y-auto">
        {navGroups.map((group, groupIdx) => (
          <div key={groupIdx} className="mb-10 px-8">
            <h3 className="gw-section-header mb-4">
              {group.label}
            </h3>
            <ul className="space-y-3">
              {group.items.map((item, itemIdx) => {
                const isActive = pathname === item.href;
                return (
                  <li key={itemIdx}>
                    <Link
                      href={item.href}
                      className={`relative flex items-center py-0.5 text-[14px] transition-colors ${
                        isActive ? 'text-black font-medium' : 'text-zinc-500 hover:text-black'
                      }`}
                    >
                      {isActive && (
                        <div className="absolute -left-5 w-1.5 h-1.5 bg-[#ff7759] rounded-full"></div>
                      )}
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="p-6 border-t border-[#e0e0e0]/60 space-y-3">
        <Link href="/" className="flex items-center gap-2 text-[12px] font-medium text-zinc-500 hover:text-[#212121] transition-colors">
          <span>Back to home</span>
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 text-[12px] font-medium text-zinc-500 hover:text-[#ff7759] transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span>Log out</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
