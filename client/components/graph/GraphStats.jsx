"use client";

import React, { useState, useEffect } from 'react';
import { getGraphStats } from '@/lib/api';

/**
 * Graph Stats Component
 * Displays node and relationship counts from Neo4j
 */
export default function GraphStats() {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getGraphStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="bg-white border border-[#e0e0e0] rounded-lg p-8">
        <p className="text-[13px] text-zinc-400 text-center">Loading graph statistics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-[13px] text-red-800">Error: {error}</p>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  const totalNodes = stats.nodes?.reduce((sum, n) => sum + (n.count || 0), 0) || 0;
  const totalRelationships = stats.relationships?.reduce((sum, r) => sum + (r.count || 0), 0) || 0;

  return (
    <div className="bg-white border border-[#e0e0e0] rounded-lg p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-[13px] font-bold text-[#39594d] uppercase tracking-wider font-mono">
          Graph Statistics
        </h3>
        <button
          onClick={loadStats}
          className="text-[11px] font-bold text-zinc-400 hover:text-black uppercase tracking-wider transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Totals */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-4">
          <p className="text-[11px] text-zinc-400 uppercase tracking-wider font-mono mb-1">Total Nodes</p>
          <p className="text-[28px] font-bold text-black">{totalNodes.toLocaleString()}</p>
        </div>
        <div className="bg-[#fafafa] border border-[#e0e0e0] rounded-lg p-4">
          <p className="text-[11px] text-zinc-400 uppercase tracking-wider font-mono mb-1">Total Edges</p>
          <p className="text-[28px] font-bold text-black">{totalRelationships.toLocaleString()}</p>
        </div>
      </div>

      {/* Nodes Breakdown */}
      <div className="mb-6">
        <h4 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 font-mono">
          Nodes by Label
        </h4>
        <div className="space-y-2">
          {stats.nodes?.map((node, idx) => (
            <div key={idx} className="flex items-center justify-between py-2 border-b border-zinc-50">
              <span className="text-[13px] font-bold text-black">{node.label}</span>
              <span className="text-[13px] text-zinc-500 font-mono">{node.count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Relationships Breakdown */}
      <div>
        <h4 className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider mb-3 font-mono">
          Relationships by Type
        </h4>
        <div className="space-y-2">
          {stats.relationships?.map((rel, idx) => (
            <div key={idx} className="flex items-center justify-between py-2 border-b border-zinc-50">
              <span className="text-[13px] font-bold text-black">{rel.relationshipType}</span>
              <span className="text-[13px] text-zinc-500 font-mono">{rel.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
