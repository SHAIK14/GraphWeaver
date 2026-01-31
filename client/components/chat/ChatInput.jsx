"use client";

import React, { useState, useRef } from 'react';

/**
 * Chat Input - helper hides after first send; disabled state links to checkpoint
 */
export default function ChatInput({ onSend, isLoading, disabled = false }) {
  const [inputValue, setInputValue] = useState('');
  const [hasSentOnce, setHasSentOnce] = useState(false);
  const inputRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputValue.trim() && !isLoading && !disabled) {
      onSend(inputValue);
      setInputValue('');
      setHasSentOnce(true);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const scrollToCheckpoint = () => {
    const el = document.querySelector('[role="region"][aria-label*="Checkpoint"]');
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  return (
    <div className="p-8 pt-4 bg-gradient-to-t from-[#fcfaf7] via-[#fcfaf7] to-transparent">
      {disabled && (
        <p className="text-[12px] text-zinc-500 mb-2 text-center">
          <button
            type="button"
            onClick={scrollToCheckpoint}
            className="text-[#39594d] font-medium hover:underline focus:outline-none focus:ring-2 focus:ring-[#39594d]/30 rounded"
          >
            ↑ Respond to the card above
          </button>
        </p>
      )}
      <form onSubmit={handleSubmit}>
        <div
          className={`relative rounded-xl p-1 flex items-center transition-all ${
            disabled
              ? 'border-2 border-dashed border-zinc-300 bg-zinc-50/80'
              : 'border-2 border-[#212121] bg-white shadow-sm focus-within:ring-2 focus-within:ring-[#212121]/10'
          }`}
        >
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? 'Use the buttons above to continue' : 'Type your message...'}
            disabled={isLoading || disabled}
            className="flex-1 bg-transparent border-none focus:ring-0 py-3 px-4 text-[15px] text-black placeholder:text-zinc-400 disabled:opacity-70 rounded-lg"
            aria-label={disabled ? 'Input disabled; respond to checkpoint above' : 'Message'}
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
      {!hasSentOnce && !disabled && (
        <p className="text-[11px] text-zinc-400 mt-2 text-center">
          <kbd className="px-1.5 py-0.5 bg-zinc-100 rounded text-[10px] font-mono">Enter</kbd> to send
        </p>
      )}
    </div>
  );
}
