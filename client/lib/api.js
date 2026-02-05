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
// FILE UPLOAD
// =============================================================================

/**
 * Upload a file (CSV, JSON, PDF) to the session
 *
 * @param {string} sessionId - Session ID
 * @param {File} file - File object from input
 * @returns {Promise<object>} Upload result with file_id, preview, etc.
 */
export async function uploadFile(sessionId, file) {
  const headers = await getHeaders();
  // Don't set Content-Type - browser will set it with boundary for multipart

  delete headers['Content-Type']; // Remove JSON content type

  // Add session ID header
  headers['x-session-id'] = sessionId;

  const formData = new FormData();
  formData.append('file', file);

  console.log('[API] Uploading file:', file.name, 'to session:', sessionId);

  const res = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    headers,
    body: formData
  });

  if (!res.ok) {
    const errorText = await res.text();
    console.error('[API] Upload error:', errorText);
    throw new Error(`Upload failed: ${res.status} - ${errorText}`);
  }

  const result = await res.json();
  console.log('[API] Upload success:', result);
  return result;
}

/**
 * Remove a file from the session
 *
 * @param {string} sessionId - Session ID
 * @param {string} fileName  - Name of the file to remove
 */
export async function removeFile(sessionId, fileName) {
  const headers = await getHeaders();
  headers['x-session-id'] = sessionId;

  const res = await fetch(`${API_BASE}/api/upload/${encodeURIComponent(fileName)}`, {
    method: 'DELETE',
    headers,
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Remove failed: ${res.status} - ${errorText}`);
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

