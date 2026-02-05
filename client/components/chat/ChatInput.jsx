"use client";

import React, { useState, useRef } from 'react';
import { uploadFile } from '@/lib/api';

/**
 * Chat Input - includes file upload button (paperclip icon)
 */
export default function ChatInput({ onSend, isLoading, disabled = false, sessionId, mode = 'build', onFileUpload, uploadedFiles = [], onRemoveFile }) {
  const [inputValue, setInputValue] = useState('');
  const [hasSentOnce, setHasSentOnce] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

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

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    setIsUploading(true);
    setUploadError(null);

    for (const file of files) {
      try {
        const result = await uploadFile(sessionId, file);

        // Notify parent component (shows "✓ Uploaded filename" in chat)
        if (onFileUpload) {
          onFileUpload(result);
        }
      } catch (error) {
        console.error('[ChatInput] File upload error:', error);
        setUploadError(`Failed to upload ${file.name}: ${error.message}`);
      }
    }

    setIsUploading(false);
    // Clear file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
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

      {/* Upload error message */}
      {uploadError && (
        <div className="mb-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-[12px] text-red-700">{uploadError}</p>
        </div>
      )}

      {/* Uploaded files - shown above text box for current session */}
      {uploadedFiles.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {uploadedFiles.map((file) => (
            <div
              key={file.name}
              className="flex items-center gap-2 px-3 py-1.5 bg-white border border-[#e0e0e0] rounded-lg text-[13px] text-zinc-700 shadow-sm"
            >
              <span className="text-[16px]">{file.type === 'csv' ? '📊' : file.type === 'json' ? '📋' : '📄'}</span>
              <span className="font-medium">{file.name}</span>
              <button
                type="button"
                onClick={() => onRemoveFile?.(file.name)}
                className="ml-1 text-zinc-400 hover:text-red-600 transition-colors"
                aria-label={`Remove ${file.name}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div
          className={`relative rounded-xl p-1 flex items-center transition-all ${
            disabled
              ? 'border-2 border-dashed border-zinc-300 bg-zinc-50/80'
              : 'border-2 border-[#212121] bg-white shadow-sm focus-within:ring-2 focus-within:ring-[#212121]/10'
          }`}
        >
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.json,.pdf,.md,.txt,.xlsx"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            aria-label="Upload files"
          />

          {/* Paperclip button - only in BUILD mode */}
          {mode === 'build' && (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading || disabled || isUploading}
              className="ml-2 p-2 text-zinc-500 hover:text-[#212121] hover:bg-zinc-100 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Attach files"
              title="Upload CSV, JSON, PDF, MD, TXT, or Excel files"
            >
              {isUploading ? (
                <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              )}
            </button>
          )}

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
