import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { ChevronDown, Plus } from 'lucide-react';
import { getCategories } from '@/api/products';
import { cachedFetch } from '@/lib/staticCache';
import { useI18n } from '@/i18n/useI18n';

interface CategoryComboboxProps {
  value: string;
  onChange: (value: string) => void;
  maxLength?: number;
  required?: boolean;
  disabled?: boolean;
  className?: string;
}

function normalizeForMatch(value: string): string {
  return value.trim().toLowerCase();
}

export function findCanonicalCategory(value: string, categories: string[]): string | null {
  const normalized = normalizeForMatch(value);
  if (!normalized) return null;
  return categories.find((category) => normalizeForMatch(category) === normalized) ?? null;
}

export default function CategoryCombobox({
  value,
  onChange,
  maxLength = 100,
  required = false,
  disabled = false,
  className = '',
}: CategoryComboboxProps) {
  const { t } = useI18n();
  const listboxId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [highlightIndex, setHighlightIndex] = useState(0);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await cachedFetch('categories', () => getCategories());
        if (!cancelled) {
          setCategories([...data].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' })));
        }
      } catch (error) {
        console.error('Failed to load categories:', error);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [open]);

  const trimmedQuery = query.trim();
  const canonicalMatch = findCanonicalCategory(trimmedQuery, categories);

  const filteredCategories = useMemo(() => {
    if (!trimmedQuery) return categories;
    const needle = normalizeForMatch(trimmedQuery);
    return categories.filter((category) => normalizeForMatch(category).includes(needle));
  }, [categories, trimmedQuery]);

  const showCreateOption = Boolean(trimmedQuery && !canonicalMatch);
  const optionCount = filteredCategories.length + (showCreateOption ? 1 : 0);

  const commitValue = (nextValue: string) => {
    const trimmed = nextValue.trim();
    const canonical = findCanonicalCategory(trimmed, categories);
    const resolved = canonical ?? trimmed;
    onChange(resolved);
    setQuery(resolved);
    setOpen(false);
  };

  const handleBlur = () => {
    window.setTimeout(() => {
      if (!containerRef.current?.contains(document.activeElement)) {
        if (trimmedQuery) {
          commitValue(trimmedQuery);
        } else {
          onChange('');
          setQuery('');
        }
        setOpen(false);
      }
    }, 0);
  };

  const selectOption = (index: number) => {
    if (index < filteredCategories.length) {
      commitValue(filteredCategories[index]);
      return;
    }
    if (showCreateOption) {
      commitValue(trimmedQuery);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (!open) setOpen(true);
      setHighlightIndex((prev) => (optionCount === 0 ? 0 : (prev + 1) % optionCount));
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (!open) setOpen(true);
      setHighlightIndex((prev) => (optionCount === 0 ? 0 : (prev - 1 + optionCount) % optionCount));
      return;
    }
    if (event.key === 'Enter') {
      event.preventDefault();
      if (open && optionCount > 0) {
        selectOption(highlightIndex);
      } else if (trimmedQuery) {
        commitValue(trimmedQuery);
      }
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      setOpen(false);
      setQuery(value);
      inputRef.current?.blur();
    }
  };

  useEffect(() => {
    setHighlightIndex(0);
  }, [trimmedQuery, open]);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-autocomplete="list"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            onChange(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          disabled={disabled || loading}
          required={required}
          maxLength={maxLength}
          placeholder={t('assets.categoryCombobox.placeholder')}
          className="w-full rounded-lg border border-gray-300 px-4 py-2 pr-10 text-sm focus:border-transparent focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
        />
        <ChevronDown
          className={`pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden
        />
      </div>

      {open && !disabled && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
        >
          {loading && (
            <li className="px-3 py-2 text-sm text-gray-500">{t('assets.categoryCombobox.loading')}</li>
          )}

          {!loading && filteredCategories.length === 0 && !showCreateOption && (
            <li className="px-3 py-2 text-sm text-gray-500">{t('assets.categoryCombobox.empty')}</li>
          )}

          {!loading &&
            filteredCategories.map((category, index) => (
              <li key={category} role="presentation">
                <button
                  type="button"
                  role="option"
                  aria-selected={value === category}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectOption(index)}
                  className={`flex w-full items-center px-3 py-2 text-left text-sm ${
                    highlightIndex === index ? 'bg-indigo-50 text-indigo-700' : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {category}
                </button>
              </li>
            ))}

          {!loading && showCreateOption && (
            <li role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={false}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => selectOption(filteredCategories.length)}
                className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm ${
                  highlightIndex === filteredCategories.length
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-indigo-600 hover:bg-indigo-50'
                }`}
              >
                <Plus className="h-4 w-4 shrink-0" aria-hidden />
                <span>{t('assets.categoryCombobox.createNew', { name: trimmedQuery })}</span>
              </button>
            </li>
          )}

          {!loading && trimmedQuery && filteredCategories.length === 0 && !showCreateOption && (
            <li className="px-3 py-2 text-sm text-gray-500">{t('assets.categoryCombobox.noMatches')}</li>
          )}
        </ul>
      )}
    </div>
  );
}
