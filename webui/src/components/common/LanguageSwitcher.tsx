import { Globe } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const LANGUAGES = [
  { code: 'en-US', label: 'EN' },
  { code: 'zh-CN', label: '中' },
] as const;

interface LanguageSwitcherProps {
  collapsed?: boolean;
}

export default function LanguageSwitcher({ collapsed = false }: LanguageSwitcherProps) {
  const { i18n, t } = useTranslation('nav');
  const currentLang = i18n.language;

  const handleChange = (code: string) => {
    i18n.changeLanguage(code);
  };

  const toggleLanguage = () => {
    const next = currentLang === 'zh-CN' ? 'en-US' : 'zh-CN';
    i18n.changeLanguage(next);
  };

  if (collapsed) {
    return (
      <button
        onClick={toggleLanguage}
        className="flex items-center justify-center w-8 h-8 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
        title={t('switchLanguage')}
      >
        <Globe className="w-4 h-4" />
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1">
      {LANGUAGES.map(({ code, label }) => (
        <button
          key={code}
          onClick={() => handleChange(code)}
          className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
            currentLang === code
              ? 'bg-red-600 text-white'
              : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
