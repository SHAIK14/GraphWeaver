"use client";

import React from 'react';

/**
 * Schema Approval Card
 * Visual display of proposed graph schema (nodes & relationships)
 * Triggered when agent proposes schema (schema_proposal phase)
 */
export default function SchemaApprovalCard({ schema, onApprove, onRequestChanges, isDisabled = false }) {
  const { nodes = [], relationships = [] } = schema || {};

  return (
    <div className="bg-white border border-[#e0e0e0] rounded-2xl p-8 shadow-sm">
      {/* Header */}
      <div className="mb-6">
        <h4 className="text-[13px] font-bold text-[#39594d] uppercase tracking-wider mb-2 font-mono">
          Proposed Schema
        </h4>
        <p className="text-[14px] text-zinc-500">
          Review the graph structure before construction.
        </p>
      </div>

      {/* Nodes Section */}
      <div className="mb-8">
        <h5 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-4 font-mono">
          Nodes ({nodes.length})
        </h5>
        <div className="grid grid-cols-2 gap-4">
          {nodes.map((node, idx) => (
            <div
              key={idx}
              className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-4 hover:border-zinc-400 transition-all"
            >
              {/* Node Label */}
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded bg-[#39594d] flex items-center justify-center">
                  <span className="text-white text-[10px] font-bold">
                    {node.label?.charAt(0) || 'N'}
                  </span>
                </div>
                <h6 className="text-[14px] font-bold text-black">{node.label}</h6>
              </div>

              {/* Source File */}
              <p className="text-[11px] text-zinc-500 mb-2">
                Source: <span className="font-mono text-zinc-600">{node.source_file}</span>
              </p>

              {/* Unique Column */}
              <p className="text-[11px] text-zinc-500 mb-3">
                ID: <span className="font-mono text-zinc-600">{node.unique_column}</span>
              </p>

              {/* Properties */}
              {node.properties && node.properties.length > 0 && (
                <div className="pt-3 border-t border-zinc-200">
                  <p className="text-[10px] text-zinc-400 uppercase tracking-wider font-mono mb-2">
                    Properties
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {node.properties.map((prop, pIdx) => (
                      <span
                        key={pIdx}
                        className="px-2 py-0.5 bg-white border border-zinc-200 rounded text-[10px] text-zinc-600 font-mono"
                      >
                        {prop}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Relationships Section */}
      <div className="mb-6">
        <h5 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-4 font-mono">
          Relationships ({relationships.length})
        </h5>
        <div className="space-y-3">
          {relationships.map((rel, idx) => (
            <div
              key={idx}
              className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-4 hover:border-zinc-400 transition-all"
            >
              {/* Relationship Diagram */}
              <div className="flex items-center gap-3 mb-2">
                <span className="text-[13px] font-bold text-black">{rel.from_label}</span>
                <div className="flex-1 flex items-center gap-2">
                  <div className="flex-1 h-px bg-[#39594d]"></div>
                  <span className="px-3 py-1 bg-[#39594d] text-white text-[10px] font-bold rounded uppercase tracking-wider">
                    {rel.type}
                  </span>
                  <div className="flex-1 h-px bg-[#39594d]"></div>
                  <span className="text-[#39594d] font-bold">→</span>
                </div>
                <span className="text-[13px] font-bold text-black">{rel.to_label}</span>
              </div>

              {/* Source File */}
              <p className="text-[11px] text-zinc-500">
                Source: <span className="font-mono text-zinc-600">{rel.source_file}</span>
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3 pt-4 border-t border-zinc-100">
        <button
          onClick={onApprove}
          disabled={isDisabled}
          className="flex-1 bg-[#39594d] text-white px-6 py-3 rounded-lg text-[13px] font-bold hover:bg-opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isDisabled ? 'Schema Approved' : 'Approve Schema'}
        </button>
        {!isDisabled && onRequestChanges && (
          <button
            onClick={onRequestChanges}
            className="px-6 py-3 border border-zinc-300 text-zinc-700 rounded-lg text-[13px] font-bold hover:border-black hover:text-black transition-all"
          >
            Request Changes
          </button>
        )}
      </div>
    </div>
  );
}
