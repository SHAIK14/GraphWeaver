"use client";

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Message Bubble Component
 * Displays user, agent, or system messages with markdown support
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
    // Custom markdown components with Tailwind styling
    const markdownComponents = {
      // Headings
      h1: ({ children }) => <h1 className="text-[20px] font-bold text-black mt-4 mb-3 first:mt-0">{children}</h1>,
      h2: ({ children }) => <h2 className="text-[18px] font-bold text-black mt-4 mb-2 first:mt-0">{children}</h2>,
      h3: ({ children }) => <h3 className="text-[16px] font-semibold text-black mt-3 mb-2 first:mt-0">{children}</h3>,
      h4: ({ children }) => <h4 className="text-[15px] font-semibold text-zinc-800 mt-3 mb-1 first:mt-0">{children}</h4>,

      // Paragraphs and text
      p: ({ children }) => <p className="text-[15px] text-zinc-700 leading-relaxed mb-3 last:mb-0">{children}</p>,
      strong: ({ children }) => <strong className="font-bold text-black">{children}</strong>,
      em: ({ children }) => <em className="italic text-zinc-700">{children}</em>,

      // Lists
      ul: ({ children }) => <ul className="list-disc list-inside space-y-1 mb-3 ml-2">{children}</ul>,
      ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 mb-3 ml-2">{children}</ol>,
      li: ({ children }) => <li className="text-[14px] text-zinc-700 leading-relaxed">{children}</li>,

      // Code
      code: ({ inline, children }) =>
        inline
          ? <code className="bg-zinc-100 text-[#39594d] px-1.5 py-0.5 rounded text-[13px] font-mono">{children}</code>
          : <code className="block bg-[#fafafa] border border-[#e0e0e0] p-4 rounded-lg text-[13px] font-mono overflow-x-auto mb-3">{children}</code>,
      pre: ({ children }) => <pre className="mb-3">{children}</pre>,

      // Links
      a: ({ href, children }) => (
        <a href={href} target="_blank" rel="noopener noreferrer" className="text-[#39594d] underline hover:text-[#2d4439] transition-colors">
          {children}
        </a>
      ),

      // Blockquotes
      blockquote: ({ children }) => (
        <blockquote className="border-l-4 border-[#39594d] pl-4 py-1 my-3 text-zinc-600 italic">
          {children}
        </blockquote>
      ),

      // Horizontal rule
      hr: () => <hr className="border-t border-[#e0e0e0] my-4" />,

      // Tables
      table: ({ children }) => (
        <div className="overflow-x-auto mb-3">
          <table className="min-w-full border border-[#e0e0e0] rounded-lg">{children}</table>
        </div>
      ),
      thead: ({ children }) => <thead className="bg-[#fafafa]">{children}</thead>,
      tbody: ({ children }) => <tbody>{children}</tbody>,
      tr: ({ children }) => <tr className="border-b border-[#e0e0e0] last:border-0">{children}</tr>,
      th: ({ children }) => <th className="px-4 py-2 text-left text-[13px] font-bold text-black">{children}</th>,
      td: ({ children }) => <td className="px-4 py-2 text-[13px] text-zinc-700">{children}</td>,
    };

    return (
      <div className="flex flex-col items-start">
        <div className="max-w-[85%]">
          <div className="bg-white border border-[#e0e0e0] px-8 py-6 rounded-2xl rounded-tl-md shadow-sm">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {content}
            </ReactMarkdown>
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
