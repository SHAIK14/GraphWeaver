"use client";

import React, { useState } from 'react';
import { PHASE_METADATA } from '@/lib/types';

const SIDEBAR_WIDTH = 280;
const COLLAPSED_WIDTH = 48;

/**
 * Progress Sidebar - collapsible, no session ID in main view
 */
export default function ProgressSidebar({ currentPhase, sessionState }) {
  const [collapsed, setCollapsed] = useState(false);

  const phases = [
    { key: 'intent', label: 'Define Goal' },
    { key: 'files', label: 'Select Files' },
    { key: 'schema', label: 'Approve Schema' },
    { key: 'build', label: 'Build Graph' },
    { key: 'query', label: 'Query Graph' },
  ];

  const currentStepIndex = phases.findIndex(p => p.key === currentPhase);

  return (
    <aside
      className="h-full bg-white border-l border-[#e0e0e0] flex flex-col overflow-hidden transition-[width] duration-200"
      style={{ width: collapsed ? COLLAPSED_WIDTH : SIDEBAR_WIDTH }}
      aria-label="Build progress"
    >
      {/* Toggle + Header */}
      <div className="flex items-center justify-between border-b border-[#e0e0e0] p-4 shrink-0">
        {!collapsed && (
          <h3 className="text-[11px] font-bold text-[#39594d] tracking-[0.04em] uppercase font-mono">
            Progress
          </h3>
        )}
        <button
          type="button"
          onClick={() => setCollapsed(c => !c)}
          className="p-2 rounded-lg text-zinc-500 hover:text-[#212121] hover:bg-zinc-100 transition-colors"
          aria-label={collapsed ? 'Expand progress' : 'Collapse progress'}
        >
          <svg
            className={`w-4 h-4 transition-transform ${collapsed ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {!collapsed && (
        <>
          {/* Step Progress */}
          <div className="p-4 border-b border-[#e0e0e0] space-y-3">
            {phases.map((phase, index) => {
              const isActive = phase.key === currentPhase;
              const isCompleted = index < currentStepIndex;
              return (
                <div key={phase.key} className="flex items-center gap-3">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 ${
                    isCompleted ? 'bg-[#e8f4f0] text-[#39594d]' : isActive ? 'bg-[#39594d] text-white' : 'bg-zinc-100 text-zinc-400'
                  }`}>
                    {isCompleted ? '✓' : index + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-[13px] font-medium truncate ${isActive ? 'text-black font-bold' : isCompleted ? 'text-zinc-500' : 'text-zinc-400'}`}>
                      {phase.label}
                    </p>
                    {isActive && (
                      <p className="text-[10px] text-[#39594d] font-bold uppercase tracking-wider mt-0.5">In progress</p>
                    )}
                  </div>
                  {isActive && <div className="w-2 h-2 bg-[#ff7759] rounded-full shrink-0" />}
                </div>
              );
            })}
          </div>

          {/* Session State Preview */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {sessionState.approved_user_goal && (
              <div className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-3">
                <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-2 font-mono">Your goal</h4>
                <p className="text-[12px] text-zinc-700 leading-relaxed line-clamp-3">
                  {typeof sessionState.approved_user_goal === 'string'
                    ? sessionState.approved_user_goal
                    : sessionState.approved_user_goal.description || JSON.stringify(sessionState.approved_user_goal)}
                </p>
              </div>
            )}
            {sessionState.approved_files && sessionState.approved_files.length > 0 && (
              <div className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-3">
                <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-2 font-mono">Selected files</h4>
                <ul className="space-y-1">
                  {sessionState.approved_files.slice(0, 5).map((file, idx) => (
                    <li key={idx} className="text-[12px] text-zinc-700 flex items-center gap-2 truncate">
                      <span className="text-[#39594d] shrink-0">✓</span>
                      <span className="font-medium truncate">{file}</span>
                    </li>
                  ))}
                  {sessionState.approved_files.length > 5 && (
                    <li className="text-[11px] text-zinc-500">+{sessionState.approved_files.length - 5} more</li>
                  )}
                </ul>
              </div>
            )}
            {sessionState.approved_schema && (
              <div className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-3">
                <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-2 font-mono">Schema</h4>
                <p className="text-[12px] text-zinc-600">
                  <span className="font-bold text-black">{sessionState.approved_schema.nodes?.length || 0}</span> nodes ·{' '}
                  <span className="font-bold text-black">{sessionState.approved_schema.relationships?.length || 0}</span> relationships
                </p>
              </div>
            )}
            {sessionState.graph_construction_complete && (
              <div className="bg-[#e8f4f0] border border-[#39594d]/20 rounded-lg p-3">
                <h4 className="text-[10px] font-bold text-[#39594d] uppercase tracking-wider mb-1 font-mono">Graph ready</h4>
                <p className="text-[12px] text-zinc-700">Knowledge graph built successfully.</p>
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  );
}
