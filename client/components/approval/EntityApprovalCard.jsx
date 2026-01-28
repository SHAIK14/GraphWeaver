"use client";

import React, { useState } from 'react';

/**
 * Entity Approval Card
 * Select entity types to extract from unstructured text
 * Triggered during NER stage of unstructured_schema phase
 */
export default function EntityApprovalCard({ entities = [], onApprove, isDisabled = false }) {
  const [selectedEntities, setSelectedEntities] = useState(
    entities.map(e => e.type)
  );

  const toggleEntity = (type) => {
    if (isDisabled) return;

    setSelectedEntities(prev =>
      prev.includes(type)
        ? prev.filter(t => t !== type)
        : [...prev, type]
    );
  };

  const handleApprove = () => {
    if (selectedEntities.length === 0 || isDisabled) return;
    onApprove(selectedEntities);
  };

  return (
    <div className="bg-white border border-[#e0e0e0] rounded-2xl p-8 shadow-sm">
      {/* Header */}
      <div className="mb-6">
        <h4 className="text-[13px] font-bold text-[#39594d] uppercase tracking-wider mb-2 font-mono">
          Extracted Entity Types
        </h4>
        <p className="text-[14px] text-zinc-500">
          Select which entity types to include in the knowledge graph.
        </p>
      </div>

      {/* Entity List */}
      <div className="space-y-3 mb-6">
        {entities.map((entity, idx) => (
          <label
            key={idx}
            className={`flex items-start gap-4 p-4 border rounded-lg cursor-pointer transition-all ${
              selectedEntities.includes(entity.type)
                ? 'bg-[#e8f4f0] border-[#39594d]'
                : 'bg-[#fafafa] border-[#e0e0e0] hover:border-zinc-300'
            } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {/* Checkbox */}
            <input
              type="checkbox"
              checked={selectedEntities.includes(entity.type)}
              onChange={() => toggleEntity(entity.type)}
              disabled={isDisabled}
              className="mt-1 w-4 h-4 rounded border-2 border-[#39594d] text-[#39594d] focus:ring-[#39594d] focus:ring-offset-0 cursor-pointer disabled:cursor-not-allowed"
            />

            {/* Entity Info */}
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[14px] font-bold text-black uppercase tracking-wide">
                  {entity.type}
                </span>
                <span className="px-2 py-0.5 bg-zinc-100 text-zinc-600 text-[10px] font-bold rounded">
                  {entity.count} found
                </span>
              </div>

              {/* Examples */}
              {entity.examples && entity.examples.length > 0 && (
                <div className="bg-white border border-zinc-200 rounded px-3 py-2">
                  <p className="text-[11px] text-zinc-400 uppercase tracking-wider font-mono mb-1">
                    Examples
                  </p>
                  <p className="text-[12px] text-zinc-600">
                    {entity.examples.slice(0, 3).join(', ')}
                    {entity.examples.length > 3 && '...'}
                  </p>
                </div>
              )}
            </div>
          </label>
        ))}
      </div>

      {/* Action Button */}
      <div className="flex items-center justify-between pt-4 border-t border-zinc-100">
        <p className="text-[12px] text-zinc-500">
          {selectedEntities.length} entity type{selectedEntities.length !== 1 ? 's' : ''} selected
        </p>
        <button
          onClick={handleApprove}
          disabled={selectedEntities.length === 0 || isDisabled}
          className="bg-[#39594d] text-white px-6 py-2.5 rounded-lg text-[13px] font-bold hover:bg-opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isDisabled ? 'Approved' : 'Approve Entity Types'}
        </button>
      </div>
    </div>
  );
}
