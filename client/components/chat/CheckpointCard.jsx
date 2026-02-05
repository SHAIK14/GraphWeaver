"use client";

import React, { useState } from 'react';

/**
 * Collapsible Schema Details Component
 * Shows summary with expand/collapse for full details
 */
function SchemaDetailsCollapsible({ nodes, relationships }) {
  const [showNodes, setShowNodes] = useState(false);
  const [showRels, setShowRels] = useState(false);

  return (
    <div className="space-y-3">
      {/* Summary - always visible */}
      <div className="flex items-center gap-3 text-[14px] font-medium text-zinc-800">
        <span className="text-[#39594d]">📊</span>
        <span>
          <strong className="text-black">{nodes.length}</strong> main things · <strong className="text-black">{relationships.length}</strong> connections
        </span>
      </div>

      {/* Nodes - collapsible */}
      {nodes.length > 0 && (
        <div className="border border-[#e0e0e0] rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => setShowNodes(!showNodes)}
            className="w-full flex items-center justify-between px-4 py-3 bg-[#fafafa] hover:bg-zinc-100 transition-colors text-left"
          >
            <span className="text-[13px] font-semibold text-zinc-800 flex items-center gap-2">
              <span className="text-[#39594d] text-[10px]">{showNodes ? '▼' : '▶'}</span>
              Main Things ({nodes.length})
            </span>
            <span className="text-[10px] text-zinc-500 font-mono uppercase tracking-wider">
              {showNodes ? 'Hide' : 'Show details'}
            </span>
          </button>
          {showNodes && (
            <div className="px-4 py-3 bg-white">
              <ul className="space-y-2 text-[13px] text-zinc-700">
                {nodes.map((n, i) => {
                  const label = typeof n === 'string' ? n : (n.label || n.name);
                  const desc = typeof n === 'object' && n.description ? n.description : null;
                  const props = typeof n === 'object' && n.properties ? n.properties : null;

                  return (
                    <li key={i} className="border-l-2 border-[#39594d] pl-3 py-1">
                      <div className="font-bold text-black">{label}</div>
                      {desc && <div className="text-[12px] text-zinc-600 mt-0.5">{desc}</div>}
                      {props && props.length > 0 && (
                        <div className="text-[11px] text-zinc-500 mt-1">
                          Properties: {props.map(p => typeof p === 'string' ? p : p.name).join(', ')}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Relationships - collapsible */}
      {relationships.length > 0 && (
        <div className="border border-[#e0e0e0] rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => setShowRels(!showRels)}
            className="w-full flex items-center justify-between px-4 py-3 bg-[#fafafa] hover:bg-zinc-100 transition-colors text-left"
          >
            <span className="text-[13px] font-semibold text-zinc-800 flex items-center gap-2">
              <span className="text-[#39594d] text-[10px]">{showRels ? '▼' : '▶'}</span>
              Connections ({relationships.length})
            </span>
            <span className="text-[10px] text-zinc-500 font-mono uppercase tracking-wider">
              {showRels ? 'Hide' : 'Show details'}
            </span>
          </button>
          {showRels && (
            <div className="px-4 py-3 bg-white">
              <ul className="space-y-2 text-[13px] text-zinc-700">
                {relationships.map((r, i) => {
                  const type = typeof r === 'string' ? r : (r.type || r.name);
                  const from = typeof r === 'object' && r.from ? r.from : null;
                  const to = typeof r === 'object' && r.to ? r.to : null;
                  const desc = typeof r === 'object' && r.description ? r.description : null;

                  return (
                    <li key={i} className="border-l-2 border-[#ff7759] pl-3 py-1">
                      <div className="font-bold text-black">
                        {type}
                        {from && to && <span className="font-normal text-zinc-600 ml-2">({from} → {to})</span>}
                      </div>
                      {desc && <div className="text-[12px] text-zinc-600 mt-0.5">{desc}</div>}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Renders proposed_data in a structured way (not raw JSON).
 * Primary = approve, secondary = modify/preview, tertiary = cancel.
 */
function ProposedDataDisplay({ checkpoint, data }) {
  if (!data) return null;

  // Files: list of paths or { files: [...] }
  const files = Array.isArray(data.files) ? data.files : (data.approved_files || data.suggested_files || []);
  if (files.length > 0) {
    return (
      <ul className="space-y-2 text-[13px] text-zinc-700">
        {files.map((f, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="text-[#39594d]">✓</span>
            <span className="font-medium">{typeof f === 'string' ? f : (f.path || f.filename || f.name || JSON.stringify(f))}</span>
          </li>
        ))}
      </ul>
    );
  }

  // Schema: nodes + relationships
  const nodes = data.nodes || data.proposed_schema?.nodes || [];
  const rels = data.relationships || data.proposed_schema?.relationships || [];
  if (nodes.length > 0 || rels.length > 0) {
    return <SchemaDetailsCollapsible nodes={nodes} relationships={rels} />;
  }

  // Goal / description
  const goal = data.goal ?? data.user_goal ?? data.description ?? data.approved_user_goal;
  if (goal) {
    const text = typeof goal === 'string' ? goal : (goal.description ?? goal.text ?? JSON.stringify(goal));
    return <p className="text-[13px] text-zinc-700 leading-relaxed">{text}</p>;
  }

  // Fallback: compact key-value list instead of raw JSON
  const entries = Object.entries(data).filter(([, v]) => v != null && typeof v !== 'object');
  if (entries.length > 0) {
    return (
      <dl className="space-y-1 text-[13px]">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <dt className="text-zinc-500 font-mono text-[11px] uppercase">{k}</dt>
            <dd className="text-zinc-700">{String(v)}</dd>
          </div>
        ))}
      </dl>
    );
  }

  return (
    <pre className="bg-[#fcfaf7] p-3 rounded border border-[#e0e0e0] overflow-auto text-[12px] text-zinc-600 max-h-48">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

const CHECKPOINT_LABELS = {
  goal_approval: 'Looks good?',
  files_approval: 'Use these files?',
  schema_approval: 'Ready to build?',
  build_approval: 'Build it',
  build_confirmation: 'Confirm',
};

export default function CheckpointCard({ checkpoint, proposedData, actions, onAction }) {
  const title = CHECKPOINT_LABELS[checkpoint] || checkpoint?.replace(/_/g, ' ') || 'Confirm';

  return (
    <div
      className="mt-4 p-6 bg-white border border-[#e0e0e0] rounded-xl shadow-sm"
      role="region"
      aria-labelledby="checkpoint-title"
      aria-label={`Checkpoint: ${title}`}
    >
      <h3 id="checkpoint-title" className="text-[16px] font-semibold text-black mb-4">
        {title}
      </h3>
      {proposedData && (
        <div className="text-[13px] text-zinc-600 mb-6">
          <ProposedDataDisplay checkpoint={checkpoint} data={proposedData} />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {actions?.approve && (
          <button
            type="button"
            onClick={() => onAction('approve')}
            className="px-4 py-2.5 bg-[#39594d] text-white text-[13px] font-medium rounded-lg hover:bg-[#2d4439] transition-colors"
            aria-label={actions.approve}
          >
            {actions.approve}
          </button>
        )}
        {actions?.modify && (
          <button
            type="button"
            onClick={() => onAction('modify')}
            className="px-4 py-2.5 bg-white text-[#39594d] text-[13px] font-medium rounded-lg border border-[#39594d] hover:bg-[#f5f5f5] transition-colors"
            aria-label={actions.modify}
          >
            {actions.modify}
          </button>
        )}
        {actions?.preview && (
          <button
            type="button"
            onClick={() => onAction('preview')}
            className="px-4 py-2.5 bg-white text-[#39594d] text-[13px] font-medium rounded-lg border border-[#e0e0e0] hover:border-[#39594d] hover:bg-[#f5f5f5] transition-colors"
            aria-label={actions.preview}
          >
            {actions.preview}
          </button>
        )}
        {actions?.cancel && (
          <button
            type="button"
            onClick={() => onAction('cancel')}
            className="px-4 py-2.5 bg-transparent text-zinc-500 text-[13px] font-medium rounded-lg hover:text-zinc-700 hover:bg-zinc-100 transition-colors ml-auto"
            aria-label={actions.cancel}
          >
            {actions.cancel}
          </button>
        )}
      </div>
    </div>
  );
}
