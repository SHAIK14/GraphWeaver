"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import Logo from './Logo';

const Sidebar = () => {
  const pathname = usePathname();

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

  return (
    <aside className="w-[240px] h-screen bg-[#fafafa] border-r border-[#e0e0e0] flex flex-col pt-12 fixed left-0 top-0 z-50">
      <div className="mb-12 px-8 flex items-center gap-3">
        <Logo className="w-8 h-8" />
        <span className="text-[14px] font-bold tracking-tighter uppercase text-zinc-900 font-mono">Graphweaver</span>
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
      
      <div className="p-8 border-t border-zinc-100 bg-[#fafafa]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-zinc-200 flex items-center justify-center text-[10px] font-bold text-zinc-600 border border-zinc-300">
            AS
          </div>
          <div className="flex flex-col">
            <span className="text-[13px] font-bold text-zinc-900">Shaik Asif</span>
            <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">Pro Edition</span>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
