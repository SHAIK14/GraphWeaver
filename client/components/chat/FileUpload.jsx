"use client";

import React, { useState, useRef } from 'react';
import { uploadFile } from '@/lib/api';

/**
 * File Upload Component - Cohere-inspired minimal design
 * Supports multiple file uploads (CSV, JSON, PDF)
 */
export default function FileUpload({ sessionId, onUploadSuccess, disabled = false }) {
  const [uploading, setUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const fileInputRef = useRef(null);

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    setUploading(true);

    // Upload files sequentially
    for (const file of files) {
      try {
        const result = await uploadFile(sessionId, file);

        setUploadedFiles(prev => [...prev, {
          id: result.file_id,
          name: result.name,
          type: result.type,
          size: result.size,
          parsed: result.parsed,
          preview: result.preview
        }]);

        if (onUploadSuccess) {
          onUploadSuccess(result);
        }
      } catch (error) {
        console.error(`Failed to upload ${file.name}:`, error);
        // Continue with other files
      }
    }

    setUploading(false);
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (type) => {
    switch (type) {
      case 'csv': return '📊';
      case 'json': return '📋';
      case 'pdf': return '📄';
      default: return '📎';
    }
  };

  return (
    <div className="space-y-3">
      {/* Upload Button */}
      <div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".csv,.json,.pdf,.md,.txt,.xlsx"
          onChange={handleFileSelect}
          disabled={disabled || uploading}
          className="hidden"
          id="file-upload"
        />
        <label
          htmlFor="file-upload"
          className={`
            inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-medium
            transition-all cursor-pointer
            ${disabled || uploading
              ? 'bg-zinc-100 text-zinc-400 cursor-not-allowed'
              : 'bg-white border-2 border-[#e0e0e0] text-zinc-700 hover:border-[#39594d] hover:text-[#39594d]'
            }
          `}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          {uploading ? 'Uploading...' : 'Upload files'}
        </label>
        <p className="text-[11px] text-zinc-400 mt-1.5">
          CSV, JSON, PDF, MD, TXT, or Excel • Max 10MB each
        </p>
      </div>

      {/* Uploaded Files List */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-medium text-zinc-600 uppercase tracking-wide">
            Uploaded Files ({uploadedFiles.length})
          </p>
          <div className="space-y-1.5">
            {uploadedFiles.map((file) => (
              <div
                key={file.id}
                className="flex items-start gap-3 p-3 bg-white border border-[#e0e0e0] rounded-lg"
              >
                <span className="text-2xl flex-shrink-0">{getFileIcon(file.type)}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-zinc-900 truncate">
                      {file.name}
                    </p>
                    {file.parsed ? (
                      <span className="text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                        ✓ Parsed
                      </span>
                    ) : (
                      <span className="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                        Error
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-zinc-500 mt-0.5">
                    {file.type.toUpperCase()} • {formatFileSize(file.size)}
                  </p>
                  {file.preview && (
                    <details className="mt-2">
                      <summary className="text-[11px] text-[#39594d] cursor-pointer hover:underline">
                        Preview
                      </summary>
                      <pre className="text-[10px] text-zinc-600 mt-1.5 p-2 bg-zinc-50 rounded overflow-x-auto max-h-32">
                        {file.preview.substring(0, 200)}...
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
