"use client";

import React, { useState } from 'react';

/**
 * Collapsible Section Component
 * Used to hide/show technical details like schema nodes, relationships, etc.
 */
export default function CollapsibleSection({ title, children, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="my-3 border border-[#e0e0e0] rounded-lg overflow-hidden bg-[#fafafa]">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-zinc-100 transition-colors"
        aria-expanded={isOpen}
      >
        <span className="text-[14px] font-semibold text-zinc-800 flex items-center gap-2">
          <span className="text-[#39594d]">{isOpen ? '▼' : '▶'}</span>
          {title}
        </span>
        <span className="text-[11px] text-zinc-500 font-mono uppercase tracking-wider">
          {isOpen ? 'Hide' : 'Show'}
        </span>
      </button>
      {isOpen && (
        <div className="px-4 pb-4 pt-1">
          {children}
        </div>
      )}
    </div>
  );
}
