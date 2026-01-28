"use client";

import React from 'react';

/**
 * Message Bubble Component
 * Displays user, agent, or system messages
 */
export default function MessageBubble({ message }) {
  const { role, content, timestamp } = message;

  // Format timestamp
  const time = new Date(timestamp).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });

  // Render based on role
  if (role === 'user') {
    return (
      <div className="flex flex-col items-end">
        <div className="max-w-[80%]">
          <div className="bg-[#eef0ef] px-6 py-4 rounded-2xl rounded-tr-md">
            <p className="text-[15px] font-medium text-[#212121] leading-relaxed">
              {content}
            </p>
          </div>
          <span className="text-[10px] text-zinc-400 mt-2 mr-2 block font-mono uppercase tracking-wider">
            {time}
          </span>
        </div>
      </div>
    );
  }

  if (role === 'agent') {
    return (
      <div className="flex flex-col items-start">
        <div className="max-w-[85%]">
          <div className="bg-white border border-[#e0e0e0] px-8 py-6 rounded-2xl rounded-tl-md shadow-sm">
            <p className="text-[15px] text-zinc-700 leading-relaxed whitespace-pre-wrap">
              {content}
            </p>
          </div>
          <span className="text-[10px] text-zinc-400 mt-2 ml-2 block font-mono uppercase tracking-wider">
            Agent • {time}
          </span>
        </div>
      </div>
    );
  }

  // System messages (errors, transitions)
  if (role === 'system') {
    return (
      <div className="flex justify-center">
        <div className="bg-amber-50 border border-amber-200 px-6 py-3 rounded-lg">
          <p className="text-[13px] text-amber-800 font-medium">
            {content}
          </p>
        </div>
      </div>
    );
  }

  return null;
}
