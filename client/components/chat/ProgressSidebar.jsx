"use client";

import React from 'react';
import { PHASE_METADATA } from '@/lib/types';

/**
 * Progress Sidebar
 * Shows current phase, step progress, and accumulated state
 */
export default function ProgressSidebar({ currentPhase, sessionState }) {
  const phases = [
    { key: 'user_intent', label: 'Define Goal' },
    { key: 'file_suggestion', label: 'Select Files' },
    { key: 'schema_proposal', label: 'Approve Schema' },
    { key: 'unstructured_schema', label: 'Extract Entities' },
    { key: 'graph_construction', label: 'Build Graph' },
  ];

  const currentStepIndex = phases.findIndex(p => p.key === currentPhase);

  return (
    <aside className="w-[320px] h-full bg-white border-l border-[#e0e0e0] flex flex-col overflow-y-auto">
      {/* Header */}
      <div className="p-8 border-b border-[#e0e0e0]">
        <h3 className="text-[11px] font-bold text-[#39594d] tracking-[0.04em] uppercase mb-6 font-mono">
          Build Progress
        </h3>

        {/* Step Progress */}
        <div className="space-y-4">
          {phases.map((phase, index) => {
            const isActive = phase.key === currentPhase;
            const isCompleted = index < currentStepIndex;

            return (
              <div key={phase.key} className="flex items-center gap-3">
                {/* Step Indicator */}
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold transition-all ${
                  isCompleted
                    ? 'bg-[#e8f4f0] text-[#006f47]'
                    : isActive
                    ? 'bg-[#39594d] text-white'
                    : 'bg-zinc-100 text-zinc-400'
                }`}>
                  {isCompleted ? '✓' : index + 1}
                </div>

                {/* Step Label */}
                <div className="flex-1">
                  <p className={`text-[13px] font-medium transition-all ${
                    isActive
                      ? 'text-black font-bold'
                      : isCompleted
                      ? 'text-zinc-500'
                      : 'text-zinc-400'
                  }`}>
                    {phase.label}
                  </p>
                  {isActive && (
                    <p className="text-[10px] text-[#39594d] font-bold uppercase tracking-wider mt-0.5">
                      In Progress
                    </p>
                  )}
                </div>

                {/* Active Indicator */}
                {isActive && (
                  <div className="w-2 h-2 bg-[#ff7759] rounded-full"></div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Session State Preview */}
      <div className="flex-1 p-8 space-y-6">
        {/* Approved Goal */}
        {sessionState.approved_user_goal && (
          <div className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-4">
            <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-3 font-mono">
              Your Goal
            </h4>
            <p className="text-[13px] text-zinc-700 leading-relaxed">
              {typeof sessionState.approved_user_goal === 'string'
                ? sessionState.approved_user_goal
                : sessionState.approved_user_goal.description || JSON.stringify(sessionState.approved_user_goal)}
            </p>
          </div>
        )}

        {/* Approved Files */}
        {sessionState.approved_files && sessionState.approved_files.length > 0 && (
          <div className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-4">
            <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-3 font-mono">
              Selected Files
            </h4>
            <ul className="space-y-2">
              {sessionState.approved_files.map((file, idx) => (
                <li key={idx} className="text-[13px] text-zinc-700 flex items-center gap-2">
                  <span className="text-[#006f47]">✓</span>
                  <span className="font-medium">{file}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Approved Schema */}
        {sessionState.approved_schema && (
          <div className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-4">
            <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider mb-3 font-mono">
              Schema Approved
            </h4>
            <div className="space-y-2">
              <p className="text-[12px] text-zinc-600">
                <span className="font-bold text-black">
                  {sessionState.approved_schema.nodes?.length || 0}
                </span> node types
              </p>
              <p className="text-[12px] text-zinc-600">
                <span className="font-bold text-black">
                  {sessionState.approved_schema.relationships?.length || 0}
                </span> relationships
              </p>
            </div>
          </div>
        )}

        {/* Graph Construction Status */}
        {sessionState.graph_construction_complete && (
          <div className="bg-[#e8f4f0] border border-emerald-200 rounded-lg p-4">
            <h4 className="text-[10px] font-bold text-[#006f47] uppercase tracking-wider mb-2 font-mono">
              Graph Ready
            </h4>
            <p className="text-[13px] text-zinc-700">
              Your knowledge graph has been constructed successfully.
            </p>
          </div>
        )}
      </div>

      {/* Session Info */}
      <div className="p-8 border-t border-zinc-100">
        <p className="text-[10px] text-zinc-400 font-mono">
          Session ID: <span className="text-zinc-600">{sessionState.session_id?.slice(0, 12) || '...'}</span>
        </p>
      </div>
    </aside>
  );
}
