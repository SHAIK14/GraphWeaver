"use client";

import React from 'react';

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
    return (
      <div className="space-y-3 text-[13px] text-zinc-700">
        {nodes.length > 0 && (
          <div>
            <p className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-1">Nodes</p>
            <ul className="space-y-1">
              {nodes.slice(0, 12).map((n, i) => (
                <li key={i}>{typeof n === 'string' ? n : (n.label || n.name || JSON.stringify(n))}</li>
              ))}
              {nodes.length > 12 && <li className="text-zinc-500">+{nodes.length - 12} more</li>}
            </ul>
          </div>
        )}
        {rels.length > 0 && (
          <div>
            <p className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-1">Relationships</p>
            <ul className="space-y-1">
              {rels.slice(0, 8).map((r, i) => (
                <li key={i}>{typeof r === 'string' ? r : (r.type || r.name || JSON.stringify(r))}</li>
              ))}
              {rels.length > 8 && <li className="text-zinc-500">+{rels.length - 8} more</li>}
            </ul>
          </div>
        )}
      </div>
    );
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
  goal_approval: 'Approve goal',
  files_approval: 'Approve files',
  schema_approval: 'Approve schema',
  build_approval: 'Build graph',
  build_confirmation: 'Confirm build',
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
