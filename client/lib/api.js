/**
 * GraphWeaver API Client
 * Centralized API calls to the FastAPI backend
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
// UNIFIED CHAT ENDPOINT (NEW)
// =============================================================================

/**
 * Unified chat endpoint - Single endpoint for all interactions
 * Handles routing, checkpoints, and phase transitions automatically
 */
export async function sendUnifiedMessage(sessionId, message, action = null) {
  const res = await fetch(`${API_BASE}/api/chat/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      action  // Optional: explicit action from button click (approve/modify/cancel)
    })
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
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
