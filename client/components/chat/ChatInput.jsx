"use client";

import React, { useState } from 'react';

/**
 * Chat Input Component
 * Input field with send button at bottom of chat
 */
export default function ChatInput({ onSend, isLoading, disabled = false }) {
  const [inputValue, setInputValue] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputValue.trim() && !isLoading && !disabled) {
      onSend(inputValue);
      setInputValue('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="p-12 pt-0 bg-gradient-to-t from-[#fcfaf7] via-[#fcfaf7] to-transparent">
      <form onSubmit={handleSubmit}>
        <div className="relative border-2 border-[#212121] bg-white rounded-xl p-1 shadow-sm flex items-center focus-within:ring-2 focus-within:ring-[#212121]/10 transition-all">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? "Please respond to the checkpoint above..." : "Type your message..."}
            disabled={isLoading || disabled}
            className="flex-1 bg-transparent border-none focus:ring-0 py-3 px-4 text-[15px] text-black placeholder:text-zinc-300 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isLoading || disabled || !inputValue.trim()}
            className="bg-[#212121] text-white px-6 py-2.5 rounded-lg text-xs font-bold hover:bg-black transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </form>

      {/* Helper Text */}
      <p className="text-[11px] text-zinc-400 mt-3 text-center font-medium">
        Press <kbd className="px-1.5 py-0.5 bg-zinc-100 rounded text-[10px] font-mono">Enter</kbd> to send • <kbd className="px-1.5 py-0.5 bg-zinc-100 rounded text-[10px] font-mono">Shift + Enter</kbd> for new line
      </p>
    </div>
  );
}
