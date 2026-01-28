"use client";

import React, { useState, useEffect, useRef } from 'react';
import { sendUnifiedMessage, queryGraph } from '@/lib/api';
import { PHASE_METADATA } from '@/lib/types';
import MessageBubble from '@/components/chat/MessageBubble';
import ChatInput from '@/components/chat/ChatInput';
import ProgressSidebar from '@/components/chat/ProgressSidebar';

/**
 * Unified Chat Interface
 * Handles both BUILD (agents) and QUERY (GraphRAG) modes
 */
export default function ChatPage() {
  // Session & Phase Management
  const [sessionId] = useState(() => `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  const [currentPhase, setCurrentPhase] = useState('user_intent');
  const [mode, setMode] = useState('build'); // 'build' or 'query'

  // Chat State
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'agent',
      content: "Welcome to GraphWeaver! I'll help you build your knowledge graph. What kind of graph would you like to create?",
      timestamp: Date.now(),
    }
  ]);

  // UI State
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Session State (accumulated from agents)
  const [sessionState, setSessionState] = useState({});

  // Checkpoint State
  const [checkpointData, setCheckpointData] = useState(null);

  // Auto-scroll to bottom
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle checkpoint action buttons
  const handleCheckpointAction = async (action) => {
    setCheckpointData(null); // Clear checkpoint UI
    await handleSend(action, action); // Send action as both message and action parameter
  };

  // Handle sending messages
  const handleSend = async (messageText, action = null) => {
    if (!messageText.trim() || isLoading) return;

    // Add user message
    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageText,
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      if (mode === 'build') {
        // BUILD MODE: Use unified endpoint
        const response = await sendUnifiedMessage(sessionId, messageText, action);

        const agentMessage = {
          id: `agent-${Date.now()}`,
          role: 'agent',
          content: response.message || response.response,
          timestamp: Date.now(),
          metadata: response,
        };

        setMessages(prev => [...prev, agentMessage]);

        // Update session state (for UI display only - backend has source of truth in Redis)
        setSessionState(prev => ({ ...prev, ...response }));

        // Handle checkpoint
        if (response.awaiting_user_action && response.checkpoint) {
          setCheckpointData({
            checkpoint: response.checkpoint,
            proposedData: response.proposed_data,
            actions: response.actions,
          });
        } else {
          setCheckpointData(null);
        }

        // Backend controls phase transitions
        if (response.current_phase && response.current_phase !== currentPhase) {
          console.log(`[Frontend] Phase transition: ${currentPhase} → ${response.current_phase}`);
          setCurrentPhase(response.current_phase);
        }

        // Check if graph built → switch to query mode
        if (response.current_phase === 'query' && response.graph_built) {
          setMode('query');

          const transitionMessage = {
            id: `system-${Date.now()}`,
            role: 'system',
            content: "✓ Graph built successfully! You can now ask questions about your knowledge graph.",
            timestamp: Date.now(),
          };
          setMessages(prev => [...prev, transitionMessage]);
        }

      } else {
        // QUERY MODE: Use GraphRAG
        const result = await queryGraph(messageText, 3);

        const queryMessage = {
          id: `agent-${Date.now()}`,
          role: 'agent',
          content: result.query_result.answer,
          timestamp: Date.now(),
          metadata: result.query_result,
        };

        setMessages(prev => [...prev, queryMessage]);
      }

    } catch (err) {
      console.error('Chat error:', err);
      setError(err.message || 'Failed to send message');

      const errorMessage = {
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Error: ${err.message || 'Failed to send message'}`,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Left Column: Chat Feed */}
      <div className="flex-1 flex flex-col overflow-hidden bg-[#fcfaf7]">
        {/* Header */}
        <header className="px-12 py-8 bg-white border-b border-[#e0e0e0]">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-[20px] font-serif italic text-black tracking-tight">
              {mode === 'build' ? 'build' : 'query'}
            </span>
            {mode === 'build' && (
              <span className="text-[14px] text-zinc-400 font-medium tracking-tight">
                / {PHASE_METADATA[currentPhase]?.label || currentPhase}
              </span>
            )}
          </div>
          <p className="text-[14px] text-zinc-500">
            {mode === 'build'
              ? 'Conversational knowledge graph construction through multi-agent workflow.'
              : 'Ask questions about your knowledge graph using GraphRAG.'}
          </p>
        </header>

        {/* Messages Feed */}
        <div className="flex-1 overflow-y-auto px-12 py-8">
          <div className="max-w-4xl mx-auto space-y-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {isLoading && (
              <div className="flex items-center gap-3 text-zinc-400">
                <div className="w-2 h-2 bg-[#39594d] rounded-full animate-pulse"></div>
                <span className="text-[13px] font-medium">Agent is thinking...</span>
              </div>
            )}

            {/* Checkpoint Approval UI */}
            {checkpointData && !isLoading && (
              <div className="mt-4 p-6 bg-white border border-[#e0e0e0] rounded-lg shadow-sm">
                <div className="mb-4">
                  <h3 className="text-[16px] font-semibold text-black mb-2">
                    {checkpointData.checkpoint === 'files_approval' && 'Approve Files'}
                    {checkpointData.checkpoint === 'schema_approval' && 'Approve Schema'}
                    {checkpointData.checkpoint === 'build_approval' && 'Build Graph'}
                  </h3>
                  {checkpointData.proposedData && (
                    <div className="text-[13px] text-zinc-600 mb-4">
                      <pre className="bg-[#fcfaf7] p-3 rounded border border-[#e0e0e0] overflow-auto">
                        {JSON.stringify(checkpointData.proposedData, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  {checkpointData.actions?.approve && (
                    <button
                      onClick={() => handleCheckpointAction('approve')}
                      className="px-4 py-2 bg-[#39594d] text-white text-[13px] font-medium rounded hover:bg-[#2d4439] transition-colors"
                    >
                      {checkpointData.actions.approve}
                    </button>
                  )}
                  {checkpointData.actions?.modify && (
                    <button
                      onClick={() => handleCheckpointAction('modify')}
                      className="px-4 py-2 bg-white text-[#39594d] text-[13px] font-medium rounded border border-[#39594d] hover:bg-[#f5f5f5] transition-colors"
                    >
                      {checkpointData.actions.modify}
                    </button>
                  )}
                  {checkpointData.actions?.preview && (
                    <button
                      onClick={() => handleCheckpointAction('preview')}
                      className="px-4 py-2 bg-white text-[#39594d] text-[13px] font-medium rounded border border-[#39594d] hover:bg-[#f5f5f5] transition-colors"
                    >
                      {checkpointData.actions.preview}
                    </button>
                  )}
                  {checkpointData.actions?.cancel && (
                    <button
                      onClick={() => handleCheckpointAction('cancel')}
                      className="px-4 py-2 bg-white text-zinc-500 text-[13px] font-medium rounded border border-zinc-300 hover:bg-zinc-50 transition-colors"
                    >
                      {checkpointData.actions.cancel}
                    </button>
                  )}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Bar */}
        <ChatInput
          onSend={(text) => handleSend(text)}
          isLoading={isLoading}
          disabled={checkpointData !== null}
        />
      </div>

      {/* Right Column: Progress Sidebar */}
      <ProgressSidebar
        currentPhase={currentPhase}
        sessionState={sessionState}
      />
    </>
  );
}
