import { useEffect, useState } from 'react';
import {
  listImageProviders,
  listProviderModels,
  type ImageProvider,
  type ImageModelInfo,
} from '@/api/imageProviders';

export interface ImageModelSelection {
  image_provider_id?: string | null;
  image_model?: string | null;
}

interface ImageModelPickerProps {
  value: ImageModelSelection;
  onChange: (next: ImageModelSelection) => void;
  disabled?: boolean;
  compact?: boolean;
}

export default function ImageModelPicker({
  value,
  onChange,
  disabled = false,
  compact = false,
}: ImageModelPickerProps) {
  const [providers, setProviders] = useState<ImageProvider[]>([]);
  const [models, setModels] = useState<ImageModelInfo[]>([]);
  const [hint, setHint] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingProviders, setLoadingProviders] = useState(true);

  useEffect(() => {
    void (async () => {
      setLoadingProviders(true);
      try {
        const list = await listImageProviders();
        setProviders(list.filter((p) => p.is_active));
      } catch (e) {
        console.error('Failed to load image providers:', e);
      } finally {
        setLoadingProviders(false);
      }
    })();
  }, []);

  useEffect(() => {
    const providerId = value.image_provider_id;
    if (!providerId) {
      setModels([]);
      setHint(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoadingModels(true);
      try {
        const res = await listProviderModels(providerId);
        if (cancelled) return;
        setModels(res.models);
        setHint(res.message || null);
        const provider = providers.find((p) => p.id === providerId);
        if (!value.image_model && provider?.default_model) {
          onChange({ ...value, image_model: provider.default_model });
        }
      } catch (e) {
        if (!cancelled) {
          setModels([]);
          setHint('拉取模型失败，可手动填写 Model ID');
        }
      } finally {
        if (!cancelled) setLoadingModels(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only refetch when provider changes
  }, [value.image_provider_id]);

  const selected = models.find((m) => m.id === value.image_model);

  const wrapClass = compact
    ? 'space-y-2'
    : 'bg-white rounded-xl shadow-sm border border-gray-200 p-4 space-y-3';

  return (
    <div className={wrapClass}>
      {!compact && (
        <div>
          <div className="text-sm font-medium text-gray-700">图像模型</div>
          <p className="text-xs text-gray-500 mt-1">留空则使用系统默认（环境变量豆包或已设默认 Provider）</p>
        </div>
      )}

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Provider {loadingProviders ? '（加载中…）' : ''}
        </label>
        <select
          value={value.image_provider_id || ''}
          disabled={disabled || loadingProviders}
          onChange={(e) => {
            const id = e.target.value || null;
            const provider = providers.find((p) => p.id === id);
            onChange({
              image_provider_id: id,
              image_model: provider?.default_model || null,
            });
          }}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-100"
        >
          <option value="">系统默认</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
              {p.is_default ? '（默认）' : ''}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          Model ID {loadingModels ? '（加载中…）' : ''}
        </label>
        {models.length > 0 ? (
          <select
            value={value.image_model || ''}
            disabled={disabled || !value.image_provider_id}
            onChange={(e) =>
              onChange({ ...value, image_model: e.target.value || null })
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-100"
          >
            <option value="">请选择或下方手填</option>
            {models.map((m) => (
              <option key={m.id} value={m.id} title={m.description || undefined}>
                {m.id}
              </option>
            ))}
          </select>
        ) : null}
        <input
          type="text"
          value={value.image_model || ''}
          disabled={disabled || !value.image_provider_id}
          onChange={(e) =>
            onChange({ ...value, image_model: e.target.value || null })
          }
          placeholder={value.image_provider_id ? '手动填写 Model / Endpoint ID' : '先选择 Provider'}
          className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-100"
        />
        {selected?.description && (
          <p className="text-xs text-gray-500 mt-1 whitespace-pre-wrap">{selected.description}</p>
        )}
        {hint && <p className="text-xs text-amber-600 mt-1">{hint}</p>}
      </div>
    </div>
  );
}
