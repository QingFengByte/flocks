import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface CopyButtonProps {
  text: string;
  /** Icon size class, e.g. "w-3 h-3" or "w-3.5 h-3.5". Defaults to "w-3.5 h-3.5". */
  size?: string;
}

export default function CopyButton({ text, size = 'w-3.5 h-3.5' }: CopyButtonProps) {
  const { t } = useTranslation('common');
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0"
      title={t('button.copy')}
    >
      {copied
        ? <Check className={`${size} text-green-500`} />
        : <Copy className={size} />}
    </button>
  );
}
