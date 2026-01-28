"use client";

import React, { useState, useEffect } from 'react';
import {
  insertSampleData,
  buildLexicalGraph,
  buildSubjectGraph,
  resolveEntities,
  createVectorIndex
} from '@/lib/api';

/**
 * Graph Builder Component
 * Sequential graph construction progress tracker
 * Executes: Domain → Lexical → Subject → Resolution → Vector Index
 */
export default function GraphBuilder({ onComplete, autoStart = false }) {
  const [progress, setProgress] = useState({
    domain_graph: false,
    lexical_graph: false,
    subject_graph: false,
    entity_resolution: false,
    vector_index: false,
  });

  const [currentStep, setCurrentStep] = useState(null);
  const [error, setError] = useState(null);
  const [results, setResults] = useState({});

  const steps = [
    {
      key: 'domain_graph',
      label: 'Domain Graph',
      description: 'Importing structured data (CSV)',
      fn: insertSampleData
    },
    {
      key: 'lexical_graph',
      label: 'Lexical Graph',
      description: 'Chunking and embedding text',
      fn: () => buildLexicalGraph('/path/to/markdown/file.md') // TODO: Make dynamic
    },
    {
      key: 'subject_graph',
      label: 'Subject Graph',
      description: 'Extracting entities from chunks',
      fn: buildSubjectGraph
    },
    {
      key: 'entity_resolution',
      label: 'Entity Resolution',
      description: 'Connecting text to domain data',
      fn: resolveEntities
    },
    {
      key: 'vector_index',
      label: 'Vector Index',
      description: 'Creating semantic search index',
      fn: createVectorIndex
    },
  ];

  // Auto-start construction if enabled
  useEffect(() => {
    if (autoStart && !currentStep && !error) {
      startConstruction();
    }
  }, [autoStart]);

  const startConstruction = async () => {
    for (const step of steps) {
      setCurrentStep(step.key);

      try {
        const result = await step.fn();

        setProgress(prev => ({ ...prev, [step.key]: true }));
        setResults(prev => ({ ...prev, [step.key]: result }));

      } catch (err) {
        console.error(`Error in ${step.key}:`, err);
        setError(`Failed at ${step.label}: ${err.message}`);
        setCurrentStep(null);
        return;
      }
    }

    setCurrentStep(null);
    if (onComplete) {
      onComplete(results);
    }
  };

  const isComplete = Object.values(progress).every(v => v);

  return (
    <div className="bg-white border border-[#e0e0e0] rounded-2xl p-8 shadow-sm">
      {/* Header */}
      <div className="mb-6">
        <h4 className="text-[13px] font-bold text-[#39594d] uppercase tracking-wider mb-2 font-mono">
          Building Knowledge Graph
        </h4>
        <p className="text-[14px] text-zinc-500">
          {isComplete
            ? 'Graph construction completed successfully!'
            : error
            ? 'Construction failed. Check the logs for details.'
            : 'Executing multi-layer graph construction pipeline...'
          }
        </p>
      </div>

      {/* Progress Steps */}
      <div className="space-y-4 mb-6">
        {steps.map((step, idx) => {
          const isCompleted = progress[step.key];
          const isActive = currentStep === step.key;
          const isPending = !isCompleted && !isActive;

          return (
            <div key={step.key} className="flex items-start gap-4">
              {/* Step Indicator */}
              <div className={`w-10 h-10 rounded-full flex items-center justify-center text-[13px] font-bold flex-shrink-0 transition-all ${
                isCompleted
                  ? 'bg-[#e8f4f0] text-[#006f47]'
                  : isActive
                  ? 'bg-[#39594d] text-white animate-pulse'
                  : 'bg-zinc-100 text-zinc-400'
              }`}>
                {isCompleted ? '✓' : isActive ? '◐' : idx + 1}
              </div>

              {/* Step Info */}
              <div className="flex-1 pt-1">
                <h5 className={`text-[14px] font-bold mb-1 transition-all ${
                  isActive
                    ? 'text-black'
                    : isCompleted
                    ? 'text-zinc-600'
                    : 'text-zinc-400'
                }`}>
                  {step.label}
                </h5>
                <p className="text-[12px] text-zinc-500">{step.description}</p>

                {/* Result Info */}
                {isCompleted && results[step.key] && (
                  <div className="mt-2 text-[11px] text-[#006f47] font-medium">
                    {step.key === 'domain_graph' && results[step.key].nodes_created && (
                      <span>✓ {results[step.key].nodes_created.length} node types created</span>
                    )}
                    {step.key === 'lexical_graph' && results[step.key].chunks_stored && (
                      <span>✓ {results[step.key].chunks_stored.chunk_count} chunks stored</span>
                    )}
                    {step.key === 'subject_graph' && results[step.key].subject_graph_built && (
                      <span>✓ {results[step.key].subject_graph_built.unique_entities} entities extracted</span>
                    )}
                    {step.key === 'entity_resolution' && results[step.key].entity_resolution_complete && (
                      <span>✓ {results[step.key].entity_resolution_complete.matches_count} entities resolved</span>
                    )}
                    {step.key === 'vector_index' && (
                      <span>✓ Index created successfully</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-[13px] text-red-800 font-medium">{error}</p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center gap-3 pt-4 border-t border-zinc-100">
        {!isComplete && !currentStep && !error && (
          <button
            onClick={startConstruction}
            className="flex-1 bg-[#39594d] text-white px-6 py-3 rounded-lg text-[13px] font-bold hover:bg-opacity-90 transition-all"
          >
            Start Construction
          </button>
        )}

        {isComplete && onComplete && (
          <button
            onClick={() => window.location.href = '/query'}
            className="flex-1 bg-[#39594d] text-white px-6 py-3 rounded-lg text-[13px] font-bold hover:bg-opacity-90 transition-all"
          >
            Go to Query Interface →
          </button>
        )}

        {error && (
          <button
            onClick={() => {
              setError(null);
              setProgress({
                domain_graph: false,
                lexical_graph: false,
                subject_graph: false,
                entity_resolution: false,
                vector_index: false,
              });
              setCurrentStep(null);
            }}
            className="flex-1 border border-zinc-300 text-zinc-700 px-6 py-3 rounded-lg text-[13px] font-bold hover:border-black hover:text-black transition-all"
          >
            Retry Construction
          </button>
        )}
      </div>
    </div>
  );
}
