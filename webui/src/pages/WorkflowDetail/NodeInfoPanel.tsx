/**
 * NodeInfoPanel — 并列在对话左侧的节点信息/编辑面板
 * 当用户点击画布节点时展开，可关闭。
 */
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { X, AlertCircle, Save, Loader2 } from 'lucide-react';
import { workflowAPI, Workflow, WorkflowEdge, WorkflowNode } from '@/api/workflow';

// ─────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────

const TYPE_LABEL: Record<string, string> = {
  python: 'Python', logic: 'Logic', branch: 'Branch', loop: 'Loop',
  tool: 'Tool', llm: 'LLM', http_request: 'HTTP', subworkflow: 'SubWorkflow',
};

const TYPE_COLOR: Record<string, { badge: string; dot: string }> = {
  python:       { badge: 'text-red-600   bg-red-50   border-red-200',   dot: 'bg-red-400'   },
  logic:        { badge: 'text-emerald-600 bg-emerald-50 border-emerald-200', dot: 'bg-emerald-400' },
  branch:       { badge: 'text-amber-600  bg-amber-50  border-amber-200',  dot: 'bg-amber-400'  },
  loop:         { badge: 'text-purple-600 bg-purple-50 border-purple-200', dot: 'bg-purple-400' },
  tool:         { badge: 'text-violet-600 bg-violet-50 border-violet-200', dot: 'bg-violet-400' },
  llm:          { badge: 'text-pink-600   bg-pink-50   border-pink-200',   dot: 'bg-pink-400'   },
  http_request: { badge: 'text-teal-600   bg-teal-50   border-teal-200',   dot: 'bg-teal-400'   },
  subworkflow:  { badge: 'text-orange-600 bg-orange-50 border-orange-200', dot: 'bg-orange-400' },
};

function inferOutputKey(node: WorkflowNode): string {
  switch (node.type) {
    case 'tool': case 'llm':   return node.output_key   || 'result';
    case 'http_request':       return node.response_key || 'response';
    case 'subworkflow':        return node.output_key   || 'output';
    case 'python': case 'logic': case 'loop': return 'dict';
    default: return '';
  }
}

// ─────────────────────────────────────────────
// Atoms
// ─────────────────────────────────────────────

function NodeChip({ id }: { id: string }) {
  return (
    <code className="text-[11px] font-mono font-semibold text-red-700 bg-red-50 border border-red-100 px-1.5 py-0.5 rounded whitespace-nowrap">
      {id}
    </code>
  );
}

function FL({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-400 mb-1.5">
      {children}{required && <span className="text-red-400 ml-0.5 normal-case">*</span>}
    </p>
  );
}

const IB = 'w-full px-2.5 py-1.5 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-red-300 bg-white';

function JsonField({ label, value, onChange, placeholder }: {
  label: string; value: unknown; onChange: (v: unknown) => void; placeholder?: string;
}) {
  const { t } = useTranslation('workflow');
  const [raw, setRaw] = useState(() => value != null ? JSON.stringify(value, null, 2) : '');
  const [err, setErr] = useState('');

  useEffect(() => { setRaw(value != null ? JSON.stringify(value, null, 2) : ''); setErr(''); }, [value]);

  const handleChange = (text: string) => {
    setRaw(text);
    if (!text.trim()) { setErr(''); return; }
    try { JSON.parse(text); setErr(''); } catch { setErr(t('detail.nodeInfo.jsonFormatError')); }
  };

  const handleBlur = () => {
    if (!raw.trim()) { onChange(undefined); setErr(''); return; }
    try { onChange(JSON.parse(raw)); setErr(''); } catch { setErr(t('detail.nodeInfo.jsonFormatError')); }
  };

  const borderClass = err
    ? 'border-red-300 focus:ring-red-300'
    : raw.trim() ? 'border-green-200 focus:ring-green-300' : '';

  return (
    <div>
      <FL>{label}</FL>
      <textarea
        value={raw}
        onChange={(e) => handleChange(e.target.value)}
        onBlur={handleBlur}
        rows={3}
        className={`${IB} font-mono resize-y ${borderClass}`}
        placeholder={placeholder || '{}'}
        spellCheck={false}
      />
      {err && <p className="mt-1 text-[11px] text-red-500 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{err}</p>}
    </div>
  );
}

// ─────────────────────────────────────────────
// DataFlow — compact table
// ─────────────────────────────────────────────

function DataFlow({ node, edges }: { node: WorkflowNode; edges: WorkflowEdge[] }) {
  const { t } = useTranslation('workflow');
  const incoming = edges.filter((e) => e.to   === node.id);
  const outgoing = edges.filter((e) => e.from === node.id);
  const outputKey = inferOutputKey(node);

  return (
    <div className="rounded-xl bg-gray-50 border border-gray-100 px-3 py-3 space-y-3 text-xs">
      <div>
        <FL>{t('detail.nodeInfo.inputSources')}</FL>
        {incoming.length === 0 ? (
          <span className="text-[11px] text-gray-400 italic">{t('detail.nodeInfo.startNode')}</span>
        ) : (
          <div className="space-y-2">
            {incoming.map((edge, i) => {
              const maps   = edge.mapping ? Object.entries(edge.mapping) : [];
              const consts = edge.const   ? Object.entries(edge.const)   : [];
              return (
                <div key={i}>
                  <div className="flex items-center gap-1.5">
                    <span className="text-gray-300">←</span>
                    <NodeChip id={edge.from} />
                    {maps.length === 0 && consts.length === 0 && <span className="text-[10px] text-gray-400">{t('detail.nodeInfo.triggerOnly')}</span>}
                  </div>
                  {maps.map(([lk, src]) => (
                    <div key={lk} className="flex items-baseline gap-1 pl-4 mt-0.5 font-mono text-[11px]">
                      <span className="text-emerald-600 font-semibold">{lk}</span>
                      <span className="text-gray-300">←</span>
                      <span className="text-gray-500 truncate" title={src}>{src}</span>
                    </div>
                  ))}
                  {consts.map(([lk, v]) => (
                    <div key={lk} className="flex items-baseline gap-1 pl-4 mt-0.5 font-mono text-[11px]">
                      <span className="text-amber-600 font-semibold">{lk}</span>
                      <span className="text-gray-300">=</span>
                      <span className="text-gray-500 truncate">{JSON.stringify(v)}</span>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>
      <div className="border-t border-gray-200" />
      <div>
        <FL>{t('detail.nodeInfo.outputDests')}</FL>
        <div className="space-y-1.5">
          {outputKey && node.type !== 'branch' && (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-gray-400">{t('detail.nodeInfo.outputKeyLabel')}</span>
              <code className="text-[11px] font-mono font-semibold text-purple-600 bg-purple-50 border border-purple-100 px-1.5 py-0.5 rounded">{outputKey}</code>
            </div>
          )}
          {node.type === 'branch' && <span className="text-[11px] text-gray-400 italic">{t('detail.nodeInfo.routeByPath')}</span>}
          {outgoing.length === 0
            ? <span className="text-[11px] text-gray-400 italic">{t('detail.nodeInfo.endNode')}</span>
            : outgoing.map((e, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="text-gray-300">→</span>
                  <NodeChip id={e.to} />
                  {e.label && <span className="text-[10px] text-gray-400 italic">{e.label}</span>}
                </div>
              ))
          }
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// NodeInfoPanel
// ─────────────────────────────────────────────

export interface NodeInfoPanelProps {
  node: WorkflowNode;
  workflow: Workflow;
  width?: number;
  onClose: () => void;
  onSaved: (updated: Workflow) => void;
}

export default function NodeInfoPanel({ node, workflow, width = 260, onClose, onSaved }: NodeInfoPanelProps) {
  const { t } = useTranslation('workflow');
  const [form, setForm]       = useState<WorkflowNode>({ ...node });
  const [saving, setSaving]   = useState(false);
  const [savedOk, setSavedOk] = useState(false);
  const [saveErr, setSaveErr] = useState('');
  const [avail, setAvail]     = useState<Workflow[]>([]);

  useEffect(() => { setForm({ ...node }); setSavedOk(false); setSaveErr(''); }, [node]);

  useEffect(() => {
    if (node.type === 'subworkflow')
      workflowAPI.list({ excludeId: workflow.id }).then((r) => setAvail(r.data)).catch(() => setAvail([]));
  }, [node.type, workflow.id]);

  const set = (field: keyof WorkflowNode, value: unknown) =>
    setForm((p) => ({ ...p, [field]: value }));

  const handleSave = async () => {
    setSaving(true); setSaveErr(''); setSavedOk(false);
    try {
      const nodes = workflow.workflowJson.nodes.map((n) => n.id === form.id ? form : n);
      const res = await workflowAPI.update(workflow.id, {
        workflowJson: { ...workflow.workflowJson, nodes },
      });
      setSavedOk(true); onSaved(res.data);
      setTimeout(() => setSavedOk(false), 2500);
    } catch (e: any) {
      setSaveErr(e?.response?.data?.detail || e?.message || t('detail.nodeInfo.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const type   = form.type;
  const colors = TYPE_COLOR[type] ?? TYPE_COLOR.python;
  const isStart = node.id === workflow.workflowJson.start;
  const SL = `${IB} cursor-pointer`;

  return (
    <div
      className="flex flex-col flex-shrink-0 bg-white border-l border-gray-200 h-full overflow-hidden"
      style={{ width }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-3 border-b border-gray-100 flex-shrink-0">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${colors.dot}`} />
        <span className={`text-[11px] font-semibold px-1.5 py-0.5 rounded border ${colors.badge} flex-shrink-0`}>
          {TYPE_LABEL[type] ?? type}
        </span>
        <code className="flex-1 min-w-0 text-xs font-mono font-bold text-gray-800 truncate">{node.id}</code>
        {isStart && (
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-orange-50 text-orange-500 border border-orange-200 flex-shrink-0">{t('detail.nodeInfo.startBadge')}</span>
        )}
        <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0" title={t('detail.nodeInfo.close')}>
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-3 pt-4 pb-3 space-y-4">
        <DataFlow node={node} edges={workflow.workflowJson.edges} />

        <div className="space-y-4">
          <div>
            <FL>{t('detail.nodeInfo.description')}</FL>
            <textarea
              value={form.description ?? ''}
              onChange={(e) => set('description', e.target.value)}
              rows={2}
              className={`${IB} resize-none`}
              placeholder={t('detail.nodeInfo.descPlaceholder')}
            />
          </div>

          {(type === 'python' || type === 'logic' || type === 'loop') && (
            <div>
              <FL>{t('detail.nodeInfo.code')}</FL>
              <textarea
                value={form.code ?? ''}
                onChange={(e) => set('code', e.target.value)}
                rows={12}
                className="w-full px-2.5 py-2.5 rounded-lg text-[11px] font-mono resize-y focus:outline-none focus:ring-2 focus:ring-red-400
                           bg-[#0d1117] text-[#e6edf3] border border-[#30363d] leading-relaxed"
                placeholder={t('detail.nodeInfo.codePlaceholder')}
                spellCheck={false}
              />
            </div>
          )}

          {type === 'branch' && (
            <div>
              <FL>{t('detail.nodeInfo.branchKey')}</FL>
              <input type="text" value={form.select_key ?? ''} onChange={(e) => set('select_key', e.target.value)} className={`${IB} font-mono`} placeholder={t('detail.nodeInfo.branchKeyPlaceholder')} />
            </div>
          )}

          {(type === 'branch' || type === 'loop') && (
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input type="checkbox" checked={!!form.join} onChange={(e) => set('join', e.target.checked)} className="w-3.5 h-3.5 rounded text-red-600" />
                <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">{t('detail.nodeInfo.enableJoin')}</span>
              </label>
              {form.join && (
                <select value={form.join_mode ?? 'flat'} onChange={(e) => set('join_mode', e.target.value)} className={SL}>
                  <option value="flat">{t('detail.nodeInfo.joinModeFlat')}</option>
                  <option value="namespace">{t('detail.nodeInfo.joinModeNamespace')}</option>
                </select>
              )}
            </div>
          )}

          {type === 'tool' && (
            <>
              <div><FL required>{t('detail.nodeInfo.toolName')}</FL>
                <input type="text" value={form.tool_name ?? ''} onChange={(e) => set('tool_name', e.target.value)} className={`${IB} font-mono`} placeholder="search / read / write" />
              </div>
              <JsonField label={t('detail.nodeInfo.toolArgs')} value={form.tool_args} onChange={(v) => set('tool_args', v)} />
              <div><FL>{t('detail.nodeInfo.outputKey')}</FL>
                <input type="text" value={form.output_key ?? ''} onChange={(e) => set('output_key', e.target.value)} className={`${IB} font-mono`} placeholder={t('detail.nodeInfo.outputKeyDefaultResult')} />
              </div>
            </>
          )}

          {type === 'llm' && (
            <>
              <div><FL required>{t('detail.nodeInfo.prompt')}</FL>
                <textarea value={form.prompt ?? ''} onChange={(e) => set('prompt', e.target.value)} rows={6} className={`${IB} resize-y`} placeholder={t('detail.nodeInfo.promptPlaceholder')} />
              </div>
              <div><FL>{t('detail.nodeInfo.model')}</FL>
                <input type="text" value={form.model ?? ''} onChange={(e) => set('model', e.target.value)} className={`${IB} font-mono`} placeholder={t('detail.nodeInfo.modelPlaceholder')} />
              </div>
              <div><FL>{t('detail.nodeInfo.outputKey')}</FL>
                <input type="text" value={form.output_key ?? ''} onChange={(e) => set('output_key', e.target.value)} className={`${IB} font-mono`} placeholder={t('detail.nodeInfo.outputKeyDefaultResult')} />
              </div>
            </>
          )}

          {type === 'http_request' && (
            <>
              <div className="flex gap-2">
                <div className="w-20 flex-shrink-0">
                  <FL required>{t('detail.nodeInfo.method')}</FL>
                  <select value={form.method ?? 'GET'} onChange={(e) => set('method', e.target.value)} className={SL}>
                    {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((m) => <option key={m}>{m}</option>)}
                  </select>
                </div>
                <div className="flex-1 min-w-0"><FL required>URL</FL>
                  <input type="text" value={form.url ?? ''} onChange={(e) => set('url', e.target.value)} className={`${IB} font-mono`} placeholder="https://..." />
                </div>
              </div>
              <JsonField label={t('detail.nodeInfo.requestHeaders')} value={form.headers} onChange={(v) => set('headers', v)} />
              <JsonField label={t('detail.nodeInfo.requestBody')} value={form.body} onChange={(v) => set('body', v)} />
              <div><FL>{t('detail.nodeInfo.responseKey')}</FL>
                <input type="text" value={form.response_key ?? ''} onChange={(e) => set('response_key', e.target.value)} className={`${IB} font-mono`} placeholder={t('detail.nodeInfo.outputKeyDefaultResponse')} />
              </div>
            </>
          )}

          {type === 'subworkflow' && (
            <>
              <div><FL required>{t('detail.nodeInfo.subworkflow')}</FL>
                <select value={form.workflow_id ?? ''} onChange={(e) => set('workflow_id', e.target.value)} className={SL}>
                  <option value="">{t('detail.nodeInfo.selectWorkflow')}</option>
                  {avail.map((wf) => <option key={wf.id} value={wf.id}>{wf.name}</option>)}
                </select>
              </div>
              <JsonField label={t('detail.nodeInfo.inputMapping')} value={form.inputs_mapping} onChange={(v) => set('inputs_mapping', v)} />
              <JsonField label={t('detail.nodeInfo.inputConst')} value={form.inputs_const} onChange={(v) => set('inputs_const', v)} />
              <div><FL>{t('detail.nodeInfo.outputKey')}</FL>
                <input type="text" value={form.output_key ?? ''} onChange={(e) => set('output_key', e.target.value)} className={`${IB} font-mono`} placeholder={t('detail.nodeInfo.outputKeyDefaultOutput')} />
              </div>
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex-shrink-0 px-3 py-3 border-t border-gray-100 space-y-1.5">
        {saveErr && (
          <p className="text-[11px] text-red-500 flex items-center gap-1"><AlertCircle className="w-3 h-3 flex-shrink-0" />{saveErr}</p>
        )}
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-colors bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
        >
          {saving ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />{t('detail.nodeInfo.saving')}</>
            : savedOk ? t('detail.nodeInfo.saved')
            : <><Save className="w-3.5 h-3.5" />{t('detail.nodeInfo.saveNode')}</>}
        </button>
      </div>
    </div>
  );
}
