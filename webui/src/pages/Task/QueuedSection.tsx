import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ListTodo, Play, Pause, RotateCcw, XCircle, Trash2,
  ChevronLeft, ChevronRight, X,
} from 'lucide-react';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import EmptyState from '@/components/common/EmptyState';
import SessionChat from '@/components/common/SessionChat';
import { useToast } from '@/components/common/Toast';
import { useConfirm } from '@/components/common/ConfirmDialog';
import { useTasks } from '@/hooks/useTasks';
import { taskAPI, Task, TaskListParams } from '@/api/task';
import { StatusBadge, PriorityBadge, SourceBadge, ModeBadge, ActionButton } from './components';
import { formatTime, formatDuration, PAGE_SIZE } from './helpers';

export default function QueuedSection({ onRefreshGlobal }: { onRefreshGlobal: () => void }) {
  const { t } = useTranslation('task');
  const [filterKey, setFilterKey] = useState('all');
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedTasks, setSelectedTasks] = useState<Set<string>>(new Set());
  const [detailTask, setDetailTask] = useState<Task | null>(null);
  const toast = useToast();
  const confirm = useConfirm();

  const QUEUED_FILTERS: { key: string; label: string; filter: Partial<TaskListParams> }[] = [
    { key: 'all',       label: t('queued.filterAll'),       filter: { type: 'queued' } },
    { key: 'completed', label: t('queued.filterCompleted'), filter: { type: 'queued', status: 'completed' } },
    { key: 'failed',    label: t('queued.filterFailed'),    filter: { type: 'queued', status: 'failed' } },
  ];

  const currentFilter = QUEUED_FILTERS.find(f => f.key === filterKey)?.filter ?? {};
  const listParams: TaskListParams = { ...currentFilter, offset: page * PAGE_SIZE, limit: PAGE_SIZE };

  const { tasks, total, loading, error, refetch } = useTasks(listParams, { pollInterval: 5000 });
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Keep detailTask in sync: update from list data when available,
  // but never clear it just because the task left the current page.
  useEffect(() => {
    if (!selectedId) { setDetailTask(null); return; }
    const found = tasks.find(t => t.id === selectedId);
    if (found) setDetailTask(found);
  }, [tasks, selectedId]);

  // When the user selects a task, also fetch it directly to be sure
  // we have the latest data even if it's not on the current page.
  const fetchDetailTask = useCallback(async (taskId: string) => {
    try {
      const res = await taskAPI.get(taskId);
      setDetailTask(res.data);
    } catch { /* ignore — list sync will cover it */ }
  }, []);

  const refresh = useCallback(() => { refetch(); onRefreshGlobal(); }, [refetch, onRefreshGlobal]);

  const refreshWithDetail = useCallback(() => {
    refresh();
    if (selectedId) fetchDetailTask(selectedId);
  }, [refresh, selectedId, fetchDetailTask]);

  const handleAction = async (action: string, taskId: string) => {
    try {
      switch (action) {
        case 'cancel': await taskAPI.cancel(taskId); break;
        case 'pause':  await taskAPI.pause(taskId);  break;
        case 'resume': await taskAPI.resume(taskId); break;
        case 'retry':  await taskAPI.retry(taskId);  break;
        case 'rerun':  await taskAPI.rerun(taskId);  break;
        case 'delete': {
          const ok = await confirm({
            description: t('queued.confirmDelete'),
            variant: 'danger',
            confirmText: t('common:button.delete'),
          });
          if (!ok) return;
          await taskAPI.delete(taskId);
          if (selectedId === taskId) { setSelectedId(null); setDetailTask(null); }
          break;
        }
      }
      refresh();
      if (selectedId === taskId) fetchDetailTask(taskId);
    } catch (err: unknown) {
      toast.error(t('queued.actionFailed'), err instanceof Error ? err.message : String(err));
    }
  };

  const toggleSelect = (id: string) =>
    setSelectedTasks(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });

  const handleBatchCancel = async () => {
    if (!selectedTasks.size) return;
    const ok = await confirm({
      description: t('queued.confirmBatchCancel', { count: selectedTasks.size }),
      variant: 'warning',
      confirmText: t('queued.confirmBatchCancelBtn'),
    });
    if (!ok) return;
    await taskAPI.batchCancel([...selectedTasks]);
    setSelectedTasks(new Set());
    refresh();
  };

  const handleBatchDelete = async () => {
    if (!selectedTasks.size) return;
    const ok = await confirm({
      description: t('queued.confirmBatchDelete', { count: selectedTasks.size }),
      variant: 'danger',
      confirmText: t('common:button.delete'),
    });
    if (!ok) return;
    await taskAPI.batchDelete([...selectedTasks]);
    setSelectedTasks(new Set());
    if (selectedId && selectedTasks.has(selectedId)) { setSelectedId(null); setDetailTask(null); }
    refresh();
  };

  if (loading && tasks.length === 0) return <div className="flex justify-center py-12"><LoadingSpinner /></div>;
  if (error) return <div className="text-center py-12 text-red-500">{error}</div>;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {QUEUED_FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => { setFilterKey(f.key); setPage(0); setSelectedId(null); setDetailTask(null); }}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                filterKey === f.key ? 'bg-white text-slate-800 shadow-sm font-medium' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        {selectedTasks.size > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">{t('queued.selectedCount', { count: selectedTasks.size })}</span>
            <button onClick={handleBatchCancel} className="px-3 py-1.5 text-sm bg-yellow-50 text-yellow-700 rounded-md hover:bg-yellow-100">{t('queued.batchCancel')}</button>
            <button onClick={handleBatchDelete} className="px-3 py-1.5 text-sm bg-red-50 text-red-700 rounded-md hover:bg-red-100">{t('queued.batchDelete')}</button>
          </div>
        )}
      </div>

      <div className="flex gap-4">
        <div className={`flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden ${detailTask ? 'max-w-[58%]' : ''}`}>
          {tasks.length === 0 ? (
            <EmptyState
              icon={<ListTodo className="w-8 h-8" />}
              title={t('queued.emptyTitle')}
              description={t('queued.emptyDescription')}
            />
          ) : (
            <>
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="w-10 px-3 py-3">
                      <input
                        type="checkbox"
                        checked={tasks.length > 0 && selectedTasks.size === tasks.length}
                        onChange={() => selectedTasks.size === tasks.length ? setSelectedTasks(new Set()) : setSelectedTasks(new Set(tasks.map(t => t.id)))}
                        className="rounded border-gray-300"
                      />
                    </th>
                    <th className="text-left px-3 py-3 font-medium text-gray-600">{t('queued.colStatus')}</th>
                    <th className="text-left px-3 py-3 font-medium text-gray-600">{t('queued.colSource')}</th>
                    <th className="text-left px-3 py-3 font-medium text-gray-600">{t('queued.colName')}</th>
                    <th className="text-left px-3 py-3 font-medium text-gray-600">{t('queued.colMode')}</th>
                    <th className="text-left px-3 py-3 font-medium text-gray-600">{t('queued.colPriority')}</th>
                    <th className="text-left px-3 py-3 font-medium text-gray-600">{t('queued.colTime')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {tasks.map(task => (
                    <tr
                      key={task.id}
                      onClick={() => {
                        if (selectedId === task.id) {
                          setSelectedId(null);
                          setDetailTask(null);
                        } else {
                          setSelectedId(task.id);
                          setDetailTask(task);
                        }
                      }}
                      className={`cursor-pointer transition-colors ${selectedId === task.id ? 'bg-slate-50' : 'hover:bg-gray-50'}`}
                    >
                      <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                        <input type="checkbox" checked={selectedTasks.has(task.id)} onChange={() => toggleSelect(task.id)} className="rounded border-gray-300" />
                      </td>
                      <td className="px-3 py-3"><StatusBadge status={task.status} /></td>
                      <td className="px-3 py-3"><SourceBadge sourceType={task.source?.sourceType ?? 'user_conversation'} /></td>
                      <td className="px-3 py-3 font-medium text-gray-900 max-w-[200px] truncate">
                        {task.deliveryStatus === 'unread' && task.status === 'completed' && (
                          <span className="w-1.5 h-1.5 bg-sky-500 rounded-full inline-block mr-1.5 mb-0.5 align-middle" />
                        )}
                        {task.title}
                      </td>
                      <td className="px-3 py-3"><ModeBadge mode={task.executionMode} agent={task.agentName} /></td>
                      <td className="px-3 py-3"><PriorityBadge priority={task.priority} /></td>
                      <td className="px-3 py-3 text-gray-400 text-xs whitespace-nowrap">
                        {task.execution?.startedAt
                          ? formatTime(task.execution.startedAt)
                          : formatTime(task.createdAt)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
                <span className="text-sm text-gray-500">
                  {t('queued.pagination', { total, page: page + 1, totalPages })}
                </span>
                <div className="flex gap-2">
                  <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed">
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} className="p-1.5 rounded hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed">
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {detailTask && (
          <QueuedDetailPanel task={detailTask} onClose={() => { setSelectedId(null); setDetailTask(null); }} onAction={handleAction} onRefresh={refreshWithDetail} />
        )}
      </div>
    </div>
  );
}

function QueuedDetailPanel({ task, onClose, onAction, onRefresh }: {
  task: Task;
  onClose: () => void;
  onAction: (action: string, taskId: string) => void;
  onRefresh?: () => void;
}) {
  const { t } = useTranslation('task');
  const sessionId = task.execution?.sessionID;
  const isActive = ['queued', 'running'].includes(task.status);
  const emptyText = ['pending', 'queued'].includes(task.status)
    ? t('queued.detailWaiting')
    : t('queued.detailNoRecord');

  return (
    <div
      className="w-[42%] min-w-[320px] bg-white rounded-xl border border-gray-200 flex flex-col"
      style={{ maxHeight: 'calc(100vh - 280px)', minHeight: '480px' }}
    >
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-200 flex-shrink-0">
        <h3 className="font-semibold text-gray-900 truncate pr-2">{task.title}</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 flex-shrink-0">
          <X className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      <div className="px-5 py-3 border-b border-gray-100 flex-shrink-0 space-y-2.5">
        <div className="flex items-center gap-2 flex-wrap">
          <StatusBadge status={task.status} />
          <PriorityBadge priority={task.priority} />
          <ModeBadge mode={task.executionMode} agent={task.agentName} />
          {task.execution?.durationMs != null && (
            <span className="text-xs text-gray-400">{formatDuration(task.execution.durationMs)}</span>
          )}
        </div>

        {task.description && (
          <p className="text-xs text-gray-500 truncate" title={task.description}>{task.description}</p>
        )}

        {task.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {task.tags.map(tag => <span key={tag} className="px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">{tag}</span>)}
          </div>
        )}

        <div className="flex flex-wrap gap-1.5">
          {(task.status === 'running' || task.status === 'queued') && (
            <ActionButton icon={<Pause className="w-3 h-3" />} label={t('queued.actionPause')} onClick={() => onAction('pause', task.id)} color="yellow" />
          )}
          {task.status === 'paused' && (
            <ActionButton icon={<Play className="w-3 h-3" />} label={t('queued.actionResume')} onClick={() => onAction('resume', task.id)} color="green" />
          )}
          {!['completed', 'cancelled', 'failed'].includes(task.status) && (
            <ActionButton icon={<XCircle className="w-3 h-3" />} label={t('queued.actionCancel')} onClick={() => onAction('cancel', task.id)} color="gray" />
          )}
          {task.status === 'failed' && (
            <ActionButton icon={<RotateCcw className="w-3 h-3" />} label={t('queued.actionRetry')} onClick={() => onAction('retry', task.id)} color="blue" />
          )}
          {['completed', 'cancelled', 'failed'].includes(task.status) && (
            <ActionButton icon={<Play className="w-3 h-3" />} label={t('queued.actionRerun')} onClick={() => onAction('rerun', task.id)} color="green" />
          )}
          <ActionButton icon={<Trash2 className="w-3 h-3" />} label={t('queued.actionDelete')} onClick={() => onAction('delete', task.id)} color="red" />
        </div>
      </div>

      <SessionChat
        sessionId={sessionId}
        live={isActive}
        hideInput
        emptyText={emptyText}
        className="flex-1 min-h-0"
        onSSEEvent={(event) => {
          // task.updated fires when session_id is linked (backend emits it immediately).
          // Trigger a task-list refresh so the new sessionId propagates to this panel
          // without waiting for the next polling cycle.
          if (event.type === 'task.updated' && event.properties?.taskID === task.id) {
            onRefresh?.();
          }
        }}
      />
    </div>
  );
}
