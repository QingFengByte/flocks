import { useTranslation } from 'react-i18next';
import type { Tool } from '@/api/tool';
import type { SortState, ColumnFilters } from '../types';
import { SOURCE_BADGE, CATEGORY_LABEL_KEY } from '../constants';
import SortFilterHeader from './SortFilterHeader';
import Pagination from './Pagination';
import { EnabledBadge } from './badges';

interface ToolTableProps {
  tools: Tool[];
  sort: SortState;
  filters: ColumnFilters;
  filterOptions: Record<string, string[]>;
  currentPage: number;
  totalPages: number;
  totalCount: number;
  pageSize: number;
  onSort: (f: SortState['field']) => void;
  onToggleFilter: (f: keyof ColumnFilters, v: string) => void;
  onClearFilter: (f: keyof ColumnFilters) => void;
  onPageChange: (page: number) => void;
  onSelect: (tool: Tool, initialSection?: 'info' | 'test') => void;
}

export default function ToolTable({
  tools,
  sort,
  filters,
  filterOptions,
  currentPage,
  totalPages,
  totalCount,
  pageSize,
  onSort,
  onToggleFilter,
  onClearFilter,
  onPageChange,
  onSelect,
}: ToolTableProps) {
  const { t } = useTranslation('tool');
  const getSourceLabel = (v: string) => {
    const sb = SOURCE_BADGE[v] ?? SOURCE_BADGE.custom;
    return sb.labelKey ? t(sb.labelKey) : (sb.label ?? v);
  };
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden flex flex-col">
      <div className="overflow-x-auto flex-1">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <SortFilterHeader
                label={t('table.category')}
                field="category"
                sort={sort}
                filterValues={filterOptions.category}
                activeFilters={filters.category}
                onSort={onSort}
                onToggleFilter={onToggleFilter}
                onClearFilter={onClearFilter}
                renderLabel={(v) => t(CATEGORY_LABEL_KEY[v] ?? 'category.custom')}
              />
              <SortFilterHeader
                label={t('table.source')}
                field="source"
                sort={sort}
                filterValues={filterOptions.source}
                activeFilters={filters.source}
                onSort={onSort}
                onToggleFilter={onToggleFilter}
                onClearFilter={onClearFilter}
                renderLabel={getSourceLabel}
              />
              <SortFilterHeader
                label={t('table.provider')}
                field="source_name"
                sort={sort}
                filterValues={filterOptions.source_name}
                activeFilters={filters.source_name}
                onSort={onSort}
                onToggleFilter={onToggleFilter}
                onClearFilter={onClearFilter}
              />
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t('table.toolName')}</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t('table.description')}</th>
              <SortFilterHeader
                label={t('table.status')}
                field="enabled"
                sort={sort}
                filterValues={filterOptions.enabled}
                activeFilters={filters.enabled}
                onSort={onSort}
                onToggleFilter={onToggleFilter}
                onClearFilter={onClearFilter}
                renderLabel={(v) => (v === 'true' ? t('table.enabledLabel') : t('table.disabledLabel'))}
              />
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t('table.actions')}</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {tools.map((tool) => {
              const sb = SOURCE_BADGE[tool.source] ?? SOURCE_BADGE.custom;
              const sourceLabel = sb.labelKey ? t(sb.labelKey) : (sb.label ?? tool.source);
              return (
                <tr key={tool.name} className="hover:bg-gray-50 cursor-pointer" onClick={() => onSelect(tool)}>
                  <td className="px-6 py-4 whitespace-nowrap min-w-[80px]">
                    <span className="text-sm text-gray-700">{t(CATEGORY_LABEL_KEY[tool.category] ?? 'category.custom')}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap min-w-[80px]">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${sb.className}`}>
                      {sourceLabel}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm text-gray-700">{tool.source_name || 'Flocks'}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm font-medium text-gray-900 font-mono">{tool.name}</span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-sm text-gray-600 line-clamp-1 max-w-sm">{tool.description}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <EnabledBadge enabled={tool.enabled} />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button onClick={(e) => { e.stopPropagation(); onSelect(tool, 'test'); }} className="text-red-600 hover:text-red-900 mr-3">
                      {t('table.test')}
                    </button>
                    <button onClick={(e) => { e.stopPropagation(); onSelect(tool, 'info'); }} className="text-gray-600 hover:text-gray-900">
                      {t('table.detail')}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        totalCount={totalCount}
        pageSize={pageSize}
        onPageChange={onPageChange}
      />
    </div>
  );
}
