import { useState, useRef, useCallback } from 'react';
import { streamQuery } from '../services/api';

const initialState = {
  isStreaming: false,
  tokens: [],
  fullText: '',
  metadata: null,
  error: null,
};

/**
 * useStream — Custom hook for SSE streaming via POST fetch
 */
export function useStream() {
  const [state, setState] = useState(initialState);
  const controllerRef = useRef(null);
  const accumulatedRef = useRef('');

  const cancelStream = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
    setState((prev) => ({ ...prev, isStreaming: false }));
  }, []);

  const startStream = useCallback((queryText, sessionId = null, topK = 5) => {
    // Cancel any existing stream
    if (controllerRef.current) {
      controllerRef.current.abort();
    }

    // Reset state
    accumulatedRef.current = '';
    setState({
      isStreaming: true,
      tokens: [],
      fullText: '',
      metadata: null,
      error: null,
    });

    const onToken = (token) => {
      accumulatedRef.current += token;
      const full = accumulatedRef.current;
      setState((prev) => ({
        ...prev,
        tokens: [...prev.tokens, token],
        fullText: full,
      }));
    };

    const onComplete = (metadata) => {
      controllerRef.current = null;
      setState((prev) => ({
        ...prev,
        isStreaming: false,
        metadata,
      }));
    };

    const onError = (err) => {
      controllerRef.current = null;
      setState((prev) => ({
        ...prev,
        isStreaming: false,
        error: err,
      }));
    };

    controllerRef.current = streamQuery(
      queryText,
      sessionId,
      topK,
      onToken,
      onComplete,
      onError
    );
  }, []);

  const reset = useCallback(() => {
    cancelStream();
    accumulatedRef.current = '';
    setState(initialState);
  }, [cancelStream]);

  return {
    ...state,
    startStream,
    cancelStream,
    reset,
  };
}
