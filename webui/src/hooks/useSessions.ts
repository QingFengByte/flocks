import { useState, useEffect, useLayoutEffect, useCallback, useRef } from 'react';
import { flushSync } from 'react-dom';
import { sessionApi } from '@/api/session';
import client from '@/api/client';
import type { Session, Message, MessagePart } from '@/types';

const VISIBLE_CATEGORIES = new Set(['user', 'workflow', 'entity-config']);

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Track whether the initial fetch has completed — refetches should be silent
  const initializedRef = useRef(false);

  const fetchSessions = useCallback(async () => {
    try {
      // Only show the full-page loading state on the very first fetch.
      // Subsequent refetches (triggered by SSE events) update data silently
      // to avoid unmounting SessionChat and disrupting the active conversation.
      if (!initializedRef.current) setLoading(true);
      setError(null);
      // Fetch only root sessions: child sessions are internal and never shown
      // in the sidebar, so excluding them avoids extra payload and filtering.
      const response = await sessionApi.list({ roots: true });
      if (Array.isArray(response)) {
        setSessions(
          response.filter(
            (s: any) => (!s.category || VISIBLE_CATEGORIES.has(s.category)) && !s.parentID,
          ),
        );
      } else {
        setSessions([]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch sessions');
      setSessions([]);
    } finally {
      setLoading(false);
      initializedRef.current = true;
    }
  }, []);

  const updateSessionTitle = useCallback((sessionId: string, title: string) => {
    setSessions(prev =>
      prev.map(session =>
        session.id === sessionId ? { ...session, title } : session,
      )
    );
  }, []);

  useEffect(() => {
    fetchSessions();
  }, []);

  const removeSession = useCallback((sessionId: string) => {
    setSessions(prev => prev.filter(s => s.id !== sessionId));
  }, []);

  const removeSessions = useCallback((sessionIds: string[]) => {
    const idSet = new Set(sessionIds);
    setSessions(prev => prev.filter(s => !idSet.has(s.id)));
  }, []);

  /** Optimistically prepend a newly created session without a full refetch. */
  const addSession = useCallback((session: Session) => {
    setSessions(prev => {
      if (prev.some(s => s.id === session.id)) return prev;
      return [session, ...prev];
    });
  }, []);

  return {
    sessions,
    loading,
    error,
    refetch: fetchSessions,
    updateSessionTitle,
    removeSession,
    removeSessions,
    addSession,
  };
}

export function useSessionMessages(sessionId?: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMessages = useCallback(async () => {
    if (!sessionId) return;
    
    try {
      setLoading(true);
      setError(null);
      const response = await client.get(`/api/session/${sessionId}/message`);
      
      // Backend returns MessageWithParts[] format: { info: {...}, parts: [...] }
      // Transform to flat message structure for UI
      const messagesData = response.data.map((msg: any) => ({
        id: msg.info.id,
        sessionID: msg.info.sessionID,
        role: msg.info.role,
        parts: msg.parts || [],
        agent: msg.info.agent,
        model: msg.info.model,
        timestamp: msg.info.time?.created || Date.now(),
        finish: msg.info.finish || null,
        compacted: msg.info.compacted || null,
      }));
      
      setMessages(messagesData);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch messages');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // Reset state synchronously before paint when session changes
  // to prevent flash of welcome screen (useEffect runs AFTER paint)
  useLayoutEffect(() => {
    setMessages([]);
    setError(null);
    if (sessionId) {
      setLoading(true);
    } else {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  return {
    messages,
    loading,
    error,
    refetch: fetchMessages,
    addMessage: (message: Message) => {
      setMessages(prev => [...prev, message]);
    },
    updateMessage: (messageInfo: any) => {
      setMessages(prev => {
        const existingIndex = prev.findIndex(m => m.id === messageInfo.id);
        if (existingIndex >= 0) {
          const existing = prev[existingIndex];
          const updated = [...prev];
          updated[existingIndex] = {
            ...existing,
            ...messageInfo,
            timestamp: messageInfo.time?.created || existing.timestamp,
            // Preserve compacted/finish from the authoritative refetch data —
            // SSE events never carry these fields, so a naive spread would
            // overwrite them with undefined.
            compacted: messageInfo.compacted ?? existing.compacted,
            finish: messageInfo.finish ?? existing.finish,
          };
          return updated;
        }

        // If a user SSE message arrives and there's a temp placeholder, replace it
        // instead of appending (temp placeholder has parts=[] so no text duplication).
        if (messageInfo.role === 'user') {
          const tempIndex = prev.reduceRight(
            (found, m, i) =>
              found >= 0 ? found : m.role === 'user' && String(m.id).startsWith('temp-') ? i : -1,
            -1
          );
          if (tempIndex >= 0) {
            const updated = [...prev];
            updated[tempIndex] = {
              id: messageInfo.id,
              sessionID: messageInfo.sessionID,
              role: 'user' as const,
              parts: updated[tempIndex].parts,
              agent: messageInfo.agent,
              model: messageInfo.model,
              timestamp: messageInfo.time?.created || updated[tempIndex].timestamp,
            };
            return updated;
          }
        }

        // Add new message
        return [...prev, {
          id: messageInfo.id,
          sessionID: messageInfo.sessionID,
          role: messageInfo.role,
          parts: [],
          agent: messageInfo.agent,
          model: messageInfo.model,
          timestamp: messageInfo.time?.created || Date.now(),
        }];
      });
    },
    /**
     * 增量更新 message part（用于流式展示）
     * @param partInfo - part 对象，包含 id, messageID, sessionID, type, text 等
     * @param delta - 本次增量文本（如果有的话）
     * 
     * 使用 flushSync 强制同步更新，确保每个 chunk 立即渲染
     */
    updateMessagePart: (partInfo: any, delta?: string) => {
      flushSync(() => {
        setMessages(prev => {
          const messageIndex = prev.findIndex(m => m.id === partInfo.messageID);
          
          if (messageIndex < 0) {
            // Message 不存在，检查是否有任何未完成的assistant message
            // 如果有，使用那个message而不是创建新的（避免重复）
            let lastAssistantIndex = -1;
            for (let i = prev.length - 1; i >= 0; i--) {
              if (prev[i].role === 'assistant' && !prev[i].finish) {
                lastAssistantIndex = i;
                break;
              }
            }
            
            if (lastAssistantIndex >= 0) {
              // 更新最后一个未完成的assistant message
              const updated = [...prev];
              const message = { ...updated[lastAssistantIndex] };
              const parts = [...(message.parts || [])];
              parts.push(partInfo);
              message.parts = parts;
              updated[lastAssistantIndex] = message;
              return updated;
            }
            
            // 没有未完成的assistant message，创建新的占位 message
            return [...prev, {
              id: partInfo.messageID,
              sessionID: partInfo.sessionID,
              role: 'assistant' as const,
              parts: [partInfo],
              timestamp: Date.now(),
            }];
          }
          
          // Message 存在，更新其 parts
          const updated = [...prev];
          const message = { ...updated[messageIndex] };
          const parts = [...(message.parts || [])];
          
          const partIndex = parts.findIndex((p: any) => p.id === partInfo.id);
          
          if (partIndex < 0) {
            for (let j = parts.length - 1; j >= 0; j--) {
              if (String(parts[j].id).startsWith('temp-')) {
                parts.splice(j, 1);
              }
            }
            parts.push(partInfo);
          } else {
            // Part 存在
            if (delta && (partInfo.type === 'text' || partInfo.type === 'reasoning' || partInfo.type === 'thinking')) {
              // 有 delta，追加到现有 text（实现逐字效果）
              // text、reasoning 和 thinking 类型都支持流式更新
              const existingPart = parts[partIndex];
              parts[partIndex] = {
                ...existingPart,
                ...partInfo,
                // 使用累积的 text（后端已经累积好了）
                text: partInfo.text,
              };
            } else {
              // 无 delta 或其他类型，直接替换整个 part
              parts[partIndex] = partInfo;
            }
          }
          
          message.parts = parts;
          updated[messageIndex] = message;
          return updated;
        });
      });
    },
  };
}
