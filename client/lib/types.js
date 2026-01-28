/**
 * GraphWeaver Type Definitions
 * Type annotations for chat, agents, and graph data
 */

// =============================================================================
// AGENT PHASES
// =============================================================================

/**
 * @typedef {'user_intent' | 'file_suggestion' | 'schema_proposal' | 'unstructured_schema' | 'graph_construction' | 'completed'} AgentPhase
 */

/**
 * Phase display metadata
 * @type {Record<AgentPhase, {label: string, step: number}>}
 */
export const PHASE_METADATA = {
  user_intent: { label: 'Define Goal', step: 1 },
  file_suggestion: { label: 'Select Files', step: 2 },
  schema_proposal: { label: 'Approve Schema', step: 3 },
  unstructured_schema: { label: 'Extract Entities', step: 4 },
  graph_construction: { label: 'Build Graph', step: 5 },
  completed: { label: 'Complete', step: 6 },
};

// =============================================================================
// CHAT MESSAGES
// =============================================================================

/**
 * @typedef {Object} ChatMessage
 * @property {string} id - Unique message ID
 * @property {'user' | 'agent' | 'system'} role - Message sender
 * @property {string} content - Message text
 * @property {number} timestamp - Unix timestamp
 * @property {Object} [metadata] - Optional metadata (e.g., tool calls, approvals)
 */

// =============================================================================
// AGENT RESPONSES
// =============================================================================

/**
 * @typedef {Object} ChatResponse
 * @property {string} session_id - Session identifier
 * @property {string} response - Agent's text response
 * @property {SessionState} state - Updated session state
 */

/**
 * @typedef {Object} SessionState
 * @property {AgentPhase} current_phase - Current agent phase
 * @property {Object} [approved_user_goal] - User's approved goal
 * @property {string[]} [approved_files] - List of approved file paths
 * @property {SchemaProposal} [approved_schema] - Approved graph schema
 * @property {string[]} [approved_entities] - Approved entity types
 * @property {FactProposal[]} [approved_facts] - Approved fact patterns
 * @property {boolean} [graph_construction_complete] - Whether graph is built
 */

// =============================================================================
// FILE SUGGESTION
// =============================================================================

/**
 * @typedef {Object} FileProposal
 * @property {string} filename - File name
 * @property {string} path - Full file path
 * @property {string} type - File type (CSV, Markdown, JSON)
 * @property {string[]} preview - Sample content or column names
 * @property {boolean} suggested - Whether agent suggests this file
 */

// =============================================================================
// SCHEMA PROPOSAL
// =============================================================================

/**
 * @typedef {Object} NodeProposal
 * @property {string} label - Node label (e.g., "Supplier")
 * @property {string} source_file - Source CSV file
 * @property {string} unique_column - Unique identifier column
 * @property {string[]} properties - Node properties
 */

/**
 * @typedef {Object} RelationshipProposal
 * @property {string} type - Relationship type (e.g., "SUPPLIED_BY")
 * @property {string} from_label - Source node label
 * @property {string} to_label - Target node label
 * @property {string} source_file - Source CSV file
 * @property {string[]} [properties] - Relationship properties
 */

/**
 * @typedef {Object} SchemaProposal
 * @property {NodeProposal[]} nodes - Proposed nodes
 * @property {RelationshipProposal[]} relationships - Proposed relationships
 */

// =============================================================================
// ENTITY EXTRACTION
// =============================================================================

/**
 * @typedef {Object} EntityProposal
 * @property {string} type - Entity type (e.g., "COMPANY", "PRODUCT")
 * @property {number} count - Number of instances found
 * @property {string[]} examples - Example entity values
 */

/**
 * @typedef {Object} FactProposal
 * @property {string} subject_label - Subject entity type
 * @property {string} predicate - Relationship predicate
 * @property {string} object_label - Object entity type
 * @property {string[]} examples - Example facts
 */

// =============================================================================
// GRAPH CONSTRUCTION
// =============================================================================

/**
 * @typedef {Object} GraphBuildProgress
 * @property {boolean} domain_graph - Domain graph built
 * @property {boolean} lexical_graph - Lexical graph built
 * @property {boolean} subject_graph - Subject graph built
 * @property {boolean} entity_resolution - Entity resolution complete
 * @property {boolean} vector_index - Vector index created
 */

/**
 * @typedef {Object} GraphStats
 * @property {Object[]} nodes - Node counts by label
 * @property {Object[]} relationships - Relationship counts by type
 */

// =============================================================================
// GRAPHRAG QUERY
// =============================================================================

/**
 * @typedef {Object} QueryResult
 * @property {string} answer - Generated answer
 * @property {number} chunks_used - Number of text chunks retrieved
 * @property {EntityMention[]} entities_found - Entities mentioned in chunks
 * @property {GraphFact[]} graph_facts - Structured facts from domain graph
 * @property {string[]} sources - Source files/chunks
 */

/**
 * @typedef {Object} EntityMention
 * @property {string} name - Entity name
 * @property {string} type - Entity type
 */

/**
 * @typedef {Object} GraphFact
 * @property {string} subject - Subject node
 * @property {string} relationship - Relationship type
 * @property {string[]} objects - Related nodes
 */

// =============================================================================
// UI STATE
// =============================================================================

/**
 * @typedef {Object} UIState
 * @property {ChatMessage[]} messages - Chat message history
 * @property {string} sessionId - Current session ID
 * @property {AgentPhase} currentPhase - Current agent phase
 * @property {boolean} isLoading - Loading state
 * @property {string} [error] - Error message
 * @property {SessionState} sessionState - Accumulated session state
 */
