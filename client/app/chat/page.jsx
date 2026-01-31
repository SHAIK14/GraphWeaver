"use client";

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { sendStreamingMessage, queryGraph } from '@/lib/api';
import { PHASE_METADATA, PHASE_HINT } from '@/lib/types';
import MessageBubble from '@/components/chat/MessageBubble';
import ChatInput from '@/components/chat/ChatInput';
import ProgressSidebar from '@/components/chat/ProgressSidebar';
import CheckpointCard from '@/components/chat/CheckpointCard';

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

  const messagesEndRef = useRef(null);
  const lastSendRef = useRef({ message: null, action: null });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleRetry = () => {
    setError(null);
    const { message, action } = lastSendRef.current;
    if (message) handleSend(message, action);
  };

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
    lastSendRef.current = { message: messageText, action };

    try {
      if (mode === 'build') {
        // BUILD MODE: Use streaming endpoint
        const agentMessageId = `agent-${Date.now()}`;
        let currentContent = '';
        let thinkingStatus = '';

        await sendStreamingMessage(sessionId, messageText, {
          // Called when agent is thinking/processing
          onThinking: (status) => {
            console.log('[Chat] Thinking:', status);
            thinkingStatus = status;
            // TODO: You can update UI here to show status like:
            // - "Analyzing files..."
            // - "Designing schema..."
            // For now, we just log it
          },

          // Called for each token (word) of the response
          onToken: (delta) => {
            currentContent += delta;

            // Update or create agent message with accumulated content
            setMessages(prev => {
              const existing = prev.find(m => m.id === agentMessageId);
              if (existing) {
                return prev.map(m =>
                  m.id === agentMessageId
                    ? { ...m, content: currentContent }
                    : m
                );
              } else {
                return [...prev, {
                  id: agentMessageId,
                  role: 'agent',
                  content: currentContent,
                  timestamp: Date.now(),
                }];
              }
            });
          },

          // Called when streaming completes
          onComplete: (response) => {
            console.log('[Chat] Complete:', response);

            // Update final message with metadata
            setMessages(prev =>
              prev.map(m =>
                m.id === agentMessageId
                  ? { ...m, content: response.message, metadata: response }
                  : m
              )
            );

            // Update session state
            setSessionState(prev => ({ ...prev, ...response }));

            // Handle checkpoint
            if (response.checkpoint) {
              setCheckpointData({
                checkpoint: response.checkpoint,
                proposedData: response.proposed_data,
                actions: response.actions,
              });
            } else {
              setCheckpointData(null);
            }

            // Update phase
            if (response.phase && response.phase !== currentPhase) {
              console.log(`[Chat] Phase: ${currentPhase} → ${response.phase}`);
              setCurrentPhase(response.phase);
            }

            setIsLoading(false);
          },

          // Called on error
          onError: (errorMsg) => {
            console.error('[Chat] Error:', errorMsg);
            setError(errorMsg);

            const errorMessage = {
              id: `error-${Date.now()}`,
              role: 'system',
              content: `Error: ${errorMsg}`,
              timestamp: Date.now(),
            };
            setMessages(prev => [...prev, errorMessage]);
            setIsLoading(false);
          }
        });

      } else {
        // QUERY MODE: Use GraphRAG (non-streaming for now)
        const result = await queryGraph(messageText, 3);

        const queryMessage = {
          id: `agent-${Date.now()}`,
          role: 'agent',
          content: result.query_result.answer,
          timestamp: Date.now(),
          metadata: result.query_result,
        };

        setMessages(prev => [...prev, queryMessage]);
        setIsLoading(false);
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
      setIsLoading(false);
    }
  };

  const isFirstMessage = messages.length === 1 && messages[0].role === 'agent';

  return (
    <>
      <div className="flex-1 flex flex-col overflow-hidden bg-[#fcfaf7]">
        {/* Error bar */}
        {error && (
          <div
            className="px-8 py-3 bg-amber-50 border-b border-amber-200 flex items-center justify-between gap-4"
            role="alert"
          >
            <p className="text-[13px] text-amber-800 font-medium truncate">{error}</p>
            <button
              type="button"
              onClick={handleRetry}
              className="shrink-0 px-3 py-1.5 bg-amber-100 text-amber-800 text-[12px] font-medium rounded hover:bg-amber-200 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Header */}
        <header className="px-8 py-5 bg-white border-b border-[#e0e0e0] flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-[18px] font-serif italic text-black tracking-tight">
                {mode === 'build' ? 'build' : 'query'}
              </span>
              {mode === 'build' && (
                <span className="text-[12px] text-zinc-400 font-medium tracking-tight">
                  {PHASE_METADATA[currentPhase]?.label || currentPhase}
                </span>
              )}
              {mode === 'query' && (
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#39594d] bg-[#e8f4f0] px-2 py-0.5 rounded">
                  GraphRAG
                </span>
              )}
            </div>
            <p className="text-[13px] text-zinc-500">
              {mode === 'build'
                ? (PHASE_HINT[currentPhase] ?? 'Conversational knowledge graph workflow.')
                : 'Ask questions about your knowledge graph.'}
            </p>
          </div>
          <Link
            href="/chat"
            className="text-[12px] font-medium text-zinc-500 hover:text-[#212121] transition-colors whitespace-nowrap"
          >
            New chat
          </Link>
        </header>

        {/* Messages Feed */}
        <div className="flex-1 overflow-y-auto px-8 py-6">
          <div className="max-w-4xl mx-auto space-y-5">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {isFirstMessage && !isLoading && (
              <div className="pt-2">
                <p className="text-[12px] text-zinc-400 mb-2">Try:</p>
                <div className="flex flex-wrap gap-2">
                  {['I want to model supplier and product data', 'Build a graph from my CSV files', 'Help me design a knowledge graph for my domain'].map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => handleSend(suggestion)}
                      className="px-3 py-2 text-[13px] text-zinc-600 bg-white border border-[#e0e0e0] rounded-lg hover:border-[#39594d] hover:text-[#39594d] transition-colors text-left max-w-full truncate"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {isLoading && (
              <div className="flex items-start gap-3">
                <div className="flex gap-1 pt-1">
                  <span className="w-2 h-2 bg-[#39594d] rounded-full animate-bounce [animation-delay:0ms]" style={{ animationDuration: '0.6s' }} />
                  <span className="w-2 h-2 bg-[#39594d] rounded-full animate-bounce [animation-delay:150ms]" style={{ animationDuration: '0.6s' }} />
                  <span className="w-2 h-2 bg-[#39594d] rounded-full animate-bounce [animation-delay:300ms]" style={{ animationDuration: '0.6s' }} />
                </div>
                <div>
                  <p className="text-[14px] font-medium text-zinc-700">Thinking...</p>
                  <p className="text-[12px] text-zinc-500 mt-0.5">{PHASE_HINT[currentPhase] ?? 'Processing your message.'}</p>
                </div>
              </div>
            )}

            {/* Checkpoint Approval UI */}
            {checkpointData && !isLoading && (
              <CheckpointCard
                checkpoint={checkpointData.checkpoint}
                proposedData={checkpointData.proposedData}
                actions={checkpointData.actions}
                onAction={handleCheckpointAction}
              />
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
