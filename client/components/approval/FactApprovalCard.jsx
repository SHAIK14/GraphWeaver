"use client";

import React, { useState } from 'react';

/**
 * Fact Approval Card
 * Select fact patterns (subject-predicate-object) to extract
 * Triggered during Facts stage of unstructured_schema phase
 */
export default function FactApprovalCard({ facts = [], onApprove, isDisabled = false }) {
  const [selectedFacts, setSelectedFacts] = useState(
    facts.map((_, idx) => idx)
  );

  const toggleFact = (index) => {
    if (isDisabled) return;

    setSelectedFacts(prev =>
      prev.includes(index)
        ? prev.filter(i => i !== index)
        : [...prev, index]
    );
  };

  const handleApprove = () => {
    if (selectedFacts.length === 0 || isDisabled) return;
    const approved = facts.filter((_, idx) => selectedFacts.includes(idx));
    onApprove(approved);
  };

  return (
    <div className="bg-white border border-[#e0e0e0] rounded-2xl p-8 shadow-sm">
      {/* Header */}
      <div className="mb-6">
        <h4 className="text-[13px] font-bold text-[#39594d] uppercase tracking-wider mb-2 font-mono">
          Extracted Fact Patterns
        </h4>
        <p className="text-[14px] text-zinc-500">
          Select which relationship patterns to include in the knowledge graph.
        </p>
      </div>

      {/* Fact List */}
      <div className="space-y-3 mb-6">
        {facts.map((fact, idx) => (
          <label
            key={idx}
            className={`flex items-start gap-4 p-4 border rounded-lg cursor-pointer transition-all ${
              selectedFacts.includes(idx)
                ? 'bg-[#e8f4f0] border-[#39594d]'
                : 'bg-[#fafafa] border-[#e0e0e0] hover:border-zinc-300'
            } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {/* Checkbox */}
            <input
              type="checkbox"
              checked={selectedFacts.includes(idx)}
              onChange={() => toggleFact(idx)}
              disabled={isDisabled}
              className="mt-1 w-4 h-4 rounded border-2 border-[#39594d] text-[#39594d] focus:ring-[#39594d] focus:ring-offset-0 cursor-pointer disabled:cursor-not-allowed"
            />

            {/* Fact Info */}
            <div className="flex-1">
              {/* Fact Pattern Diagram */}
              <div className="flex items-center gap-3 mb-3">
                <span className="px-3 py-1 bg-white border border-zinc-300 rounded text-[11px] font-bold text-black uppercase">
                  {fact.subject_label}
                </span>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-px bg-[#39594d]"></div>
                  <span className="px-2 py-0.5 bg-[#39594d] text-white text-[9px] font-bold rounded uppercase tracking-wider">
                    {fact.predicate}
                  </span>
                  <div className="w-8 h-px bg-[#39594d]"></div>
                  <span className="text-[#39594d] font-bold text-sm">→</span>
                </div>
                <span className="px-3 py-1 bg-white border border-zinc-300 rounded text-[11px] font-bold text-black uppercase">
                  {fact.object_label}
                </span>
              </div>

              {/* Examples */}
              {fact.examples && fact.examples.length > 0 && (
                <div className="bg-white border border-zinc-200 rounded px-3 py-2">
                  <p className="text-[11px] text-zinc-400 uppercase tracking-wider font-mono mb-1">
                    Examples
                  </p>
                  <div className="space-y-1">
                    {fact.examples.slice(0, 2).map((example, eIdx) => (
                      <p key={eIdx} className="text-[12px] text-zinc-600 italic">
                        "{example}"
                      </p>
                    ))}
                    {fact.examples.length > 2 && (
                      <p className="text-[11px] text-zinc-400">
                        +{fact.examples.length - 2} more
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </label>
        ))}
      </div>

      {/* Action Button */}
      <div className="flex items-center justify-between pt-4 border-t border-zinc-100">
        <p className="text-[12px] text-zinc-500">
          {selectedFacts.length} fact pattern{selectedFacts.length !== 1 ? 's' : ''} selected
        </p>
        <button
          onClick={handleApprove}
          disabled={selectedFacts.length === 0 || isDisabled}
          className="bg-[#39594d] text-white px-6 py-2.5 rounded-lg text-[13px] font-bold hover:bg-opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isDisabled ? 'Approved' : 'Approve Fact Patterns'}
        </button>
      </div>
    </div>
  );
}
