import type { Tool } from '@/api/tool';

export function getLocalizedToolDescription(tool: Pick<Tool, 'description' | 'description_cn'>, language: string): string {
  const normalized = language.toLowerCase().replace('_', '-');
  const englishDescription = tool.description?.trim() || '';
  const chineseDescription = tool.description_cn?.trim() || '';
  if (normalized.startsWith('zh')) {
    return chineseDescription || englishDescription;
  }
  return englishDescription || chineseDescription;
}
