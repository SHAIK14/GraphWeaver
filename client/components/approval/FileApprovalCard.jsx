"use client";

import React, { useState } from 'react';

/**
 * File Approval Card
 * Inline component for selecting CSV/Markdown files to import
 * Triggered when agent proposes files (file_suggestion phase)
 */
export default function FileApprovalCard({ files = [], onApprove, isDisabled = false }) {
  const [selectedFiles, setSelectedFiles] = useState(
    files.filter(f => f.suggested).map(f => f.filename)
  );

  const toggleFile = (filename) => {
    if (isDisabled) return;

    setSelectedFiles(prev =>
      prev.includes(filename)
        ? prev.filter(f => f !== filename)
        : [...prev, filename]
    );
  };

  const handleApprove = () => {
    if (selectedFiles.length === 0 || isDisabled) return;
    onApprove(selectedFiles);
  };

  return (
    <div className="bg-white border border-[#e0e0e0] rounded-2xl p-8 shadow-sm">
      {/* Header */}
      <div className="mb-6">
        <h4 className="text-[13px] font-bold text-[#39594d] uppercase tracking-wider mb-2 font-mono">
          Available Files
        </h4>
        <p className="text-[14px] text-zinc-500">
          Select which files to use for building your knowledge graph.
        </p>
      </div>

      {/* File List */}
      <div className="space-y-3 mb-6">
        {files.map((file, idx) => (
          <label
            key={idx}
            className={`flex items-start gap-4 p-4 border rounded-lg cursor-pointer transition-all ${
              selectedFiles.includes(file.filename)
                ? 'bg-[#e8f4f0] border-[#39594d]'
                : 'bg-[#fafafa] border-[#e0e0e0] hover:border-zinc-300'
            } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {/* Checkbox */}
            <input
              type="checkbox"
              checked={selectedFiles.includes(file.filename)}
              onChange={() => toggleFile(file.filename)}
              disabled={isDisabled}
              className="mt-1 w-4 h-4 rounded border-2 border-[#39594d] text-[#39594d] focus:ring-[#39594d] focus:ring-offset-0 cursor-pointer disabled:cursor-not-allowed"
            />

            {/* File Info */}
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[14px] font-bold text-black">
                  {file.filename}
                </span>
                {file.suggested && (
                  <span className="px-2 py-0.5 bg-[#39594d] text-white text-[9px] font-bold rounded uppercase tracking-wider">
                    Suggested
                  </span>
                )}
              </div>

              {/* File Type */}
              <p className="text-[12px] text-zinc-500 mb-2">
                Type: <span className="font-medium">{file.type || 'Unknown'}</span>
              </p>

              {/* Preview */}
              {file.preview && file.preview.length > 0 && (
                <div className="bg-white border border-zinc-200 rounded px-3 py-2 mt-2">
                  <p className="text-[11px] text-zinc-400 uppercase tracking-wider font-mono mb-1">
                    Preview
                  </p>
                  <p className="text-[12px] text-zinc-600 font-mono">
                    {file.preview.join(', ')}
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
          {selectedFiles.length} file{selectedFiles.length !== 1 ? 's' : ''} selected
        </p>
        <button
          onClick={handleApprove}
          disabled={selectedFiles.length === 0 || isDisabled}
          className="bg-[#39594d] text-white px-6 py-2.5 rounded-lg text-[13px] font-bold hover:bg-opacity-90 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isDisabled ? 'Approved' : 'Approve Selected Files'}
        </button>
      </div>
    </div>
  );
}
