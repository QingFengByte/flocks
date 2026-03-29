import { Link } from 'react-router-dom';
import { ArrowLeft, PanelRight, PanelRightClose } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Workflow } from '@/api/workflow';

interface TopBarProps {
  workflow: Workflow;
  panelOpen: boolean;
  onTogglePanel: () => void;
}

export default function TopBar({ workflow, panelOpen, onTogglePanel }: TopBarProps) {
  const { t } = useTranslation('workflow');

  const statusConfig = {
    draft:    { label: t('status.draft'),    className: 'bg-gray-100 text-gray-700' },
    active:   { label: t('status.active'),   className: 'bg-green-100 text-green-800' },
    archived: { label: t('status.archived'), className: 'bg-yellow-100 text-yellow-800' },
  };

  const status = statusConfig[workflow.status];

  return (
    <div className="h-14 bg-white border-b border-gray-200 flex items-center px-4 gap-3 flex-shrink-0 z-10">
      {/* Back button */}
      <Link
        to="/workflows"
        className="flex items-center gap-1.5 text-gray-500 hover:text-gray-800 transition-colors text-sm font-medium"
      >
        <ArrowLeft className="w-4 h-4" />
        {t('pageTitle')}
      </Link>

      <div className="w-px h-5 bg-gray-200" />

      {/* Workflow name + status */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <h1 className="text-sm font-semibold text-gray-900 truncate">{workflow.name}</h1>
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ${status.className}`}>
          {status.label}
        </span>
        {workflow.category && workflow.category !== 'default' && (
          <span className="text-xs text-gray-400 flex-shrink-0">{workflow.category}</span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onTogglePanel}
          className="flex items-center justify-center w-8 h-8 border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 transition-colors"
          title={panelOpen ? t('detail.topBar.collapsePanel') : t('detail.topBar.expandPanel')}
        >
          {panelOpen ? (
            <PanelRightClose className="w-4 h-4" />
          ) : (
            <PanelRight className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  );
}
