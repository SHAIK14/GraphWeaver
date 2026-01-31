/**
 * GraphWeaver API Client
 * Centralized API calls to the FastAPI backend
 */

import { getAccessToken } from './auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Get headers with JWT token
 */
async function getHeaders() {
  const token = await getAccessToken();
  console.log('[API] Token:', token ? `${token.substring(0, 20)}...` : 'No token');

  const headers = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  } else {
    console.warn('[API] No token available for request');
  }

  return headers;
}

// =============================================================================
// AGENT ENDPOINTS
// =============================================================================

/**
 * User Intent Agent - Define graph goal
 */
export async function chatUserIntent(sessionId, message) {
  const res = await fetch(`${API_BASE}/api/user-intent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message })
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

/**
 * File Suggestion Agent - Select files to import
 * No longer needs approvedUserGoal - loaded from Redis automatically
 */
export async function chatFileSuggestion(sessionId, message) {
  const res = await fetch(`${API_BASE}/api/file-suggestion/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message
    })
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

/**
 * Schema Proposal Agent - Approve graph schema
 * No longer needs context params - loaded from Redis automatically
 */
export async function chatSchemaProposal(sessionId, message) {
  const res = await fetch(`${API_BASE}/api/schema-proposal/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message
    })
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

/**
 * Unstructured Schema Agent - Extract entities and facts
 * No longer needs context params - loaded from Redis automatically
 */
export async function chatUnstructuredSchema(sessionId, message) {
  const res = await fetch(`${API_BASE}/api/unstructured-schema/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message
    })
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

// =============================================================================
// GRAPH CONSTRUCTION
// =============================================================================

/**
 * Insert sample domain data (for testing)
 */
export async function insertSampleData() {
  const res = await fetch(`${API_BASE}/api/graph-construction/sample-data`, {
    method: 'POST'
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

/**
 * Build lexical graph from markdown file
 */
export async function buildLexicalGraph(filePath) {
  const res = await fetch(`${API_BASE}/api/graph-construction/lexical`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_path: filePath })
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

/**
 * Build subject graph (extract entities from chunks)
 */
export async function buildSubjectGraph(sourceFile = null) {
  const res = await fetch(`${API_BASE}/api/graph-construction/subject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_file: sourceFile })
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

/**
 * Resolve entities (connect subject graph to domain graph)
 */
export async function resolveEntities() {
  const res = await fetch(`${API_BASE}/api/graph-construction/resolve-entities`, {
    method: 'POST'
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

/**
 * Create vector index for semantic search
 */
export async function createVectorIndex() {
  const res = await fetch(`${API_BASE}/api/graph-construction/create-vector-index`, {
    method: 'POST'
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

/**
 * Get graph statistics
 */
export async function getGraphStats() {
  const res = await fetch(`${API_BASE}/api/graph-construction/stats`);

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

/**
 * Clear entire graph
 */
export async function clearGraph() {
  const res = await fetch(`${API_BASE}/api/graph-construction/clear`, {
    method: 'DELETE'
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

// =============================================================================
// GRAPHRAG QUERY
// =============================================================================

/**
 * Query the knowledge graph using GraphRAG
 */
export async function queryGraph(question, topK = 3) {
  const res = await fetch(`${API_BASE}/api/graph-construction/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k: topK })
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

// =============================================================================
// UNIFIED CHAT ENDPOINT (STREAMING)
// =============================================================================

/**
 * Streaming chat endpoint - Handles SSE streaming responses
 *
 * @param {string} sessionId - Session ID
 * @param {string} message - User message
 * @param {object} callbacks - Event handlers
 * @param {function} callbacks.onThinking - Called when agent is thinking
 * @param {function} callbacks.onToken - Called for each token (word) streamed
 * @param {function} callbacks.onComplete - Called when stream completes
 * @param {function} callbacks.onError - Called on error
 */
export async function sendStreamingMessage(sessionId, message, callbacks) {
  const headers = await getHeaders();
  headers['Content-Type'] = 'application/json'; // Required for FastAPI to parse body

  console.log('[API] Streaming message to:', `${API_BASE}/api/chat`);

  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      session_id: sessionId,
      message
    })
  });

  if (!res.ok) {
    const errorText = await res.text();
    console.error('[API] Error response:', errorText);

    if (res.status === 401 || res.status === 403) {
      throw new Error('Authentication required. Please log in again.');
    }
    throw new Error(`API error: ${res.status} - ${errorText}`);
  }

  // Read the stream
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        console.log('[API] Stream complete');
        break;
      }

      // Decode chunk
      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages (end with \n\n)
      const messages = buffer.split('\n\n');
      buffer = messages.pop() || ''; // Keep incomplete message in buffer

      for (const msg of messages) {
        if (!msg.trim()) continue;

        // Parse SSE format: "event: type\ndata: {...}"
        const lines = msg.split('\n');
        let eventType = 'message';
        let data = null;

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            try {
              data = JSON.parse(line.substring(6));
            } catch (e) {
              console.error('[API] Failed to parse SSE data:', line);
            }
          }
        }

        // Call appropriate callback
        if (data) {
          console.log('[API] SSE Event:', eventType, data);

          if (eventType === 'thinking' && callbacks.onThinking) {
            callbacks.onThinking(data.content);
          } else if (eventType === 'token' && callbacks.onToken) {
            callbacks.onToken(data.delta);
          } else if (eventType === 'complete' && callbacks.onComplete) {
            callbacks.onComplete(data);
          } else if (eventType === 'error' && callbacks.onError) {
            callbacks.onError(data.message);
          }
        }
      }
    }
  } catch (error) {
    console.error('[API] Stream error:', error);
    if (callbacks.onError) {
      callbacks.onError(error.message);
    }
  }
}

// =============================================================================
// HELPER: Route message to correct agent based on phase (OLD - DEPRECATED)
// =============================================================================

/**
 * Send message to the appropriate agent based on current phase
 * Context (approved_user_goal, approved_files) now loaded from Redis automatically
 *
 * @deprecated Use sendUnifiedMessage instead
 */
export async function sendMessageToAgent(sessionId, message, currentPhase) {
  const agentMap = {
    'user_intent': (sid, msg) => chatUserIntent(sid, msg),
    'file_suggestion': (sid, msg) => chatFileSuggestion(sid, msg),
    'schema_proposal': (sid, msg) => chatSchemaProposal(sid, msg),
    'unstructured_schema': (sid, msg) => chatUnstructuredSchema(sid, msg),
  };

  const agentFunction = agentMap[currentPhase];

  if (!agentFunction) {
    throw new Error(`Unknown phase: ${currentPhase}`);
  }

  return agentFunction(sessionId, message);
}
