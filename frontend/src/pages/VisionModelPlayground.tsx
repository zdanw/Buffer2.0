import { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, ImageIcon, ImagePlus, Loader2, MessageSquare, Send, Sparkles, Trash2, User, X } from 'lucide-react';
import PageHeader from '@/components/PageHeader';
import {
  generateVisionImage,
  getVisionChatConfig,
  sendVisionChat,
  type VisionChatConfig,
  type VisionChatMessage,
} from '@/api/visionChat';

const DEFAULT_SYSTEM_PROMPT =
  '你是一个 helpful 的多模态助手。请用清晰、准确的中文回答用户问题；若用户上传图片，请结合图片内容作答。';

const IMAGE_SIZES = [
  { value: '1024x1024', label: '1024×1024（方图）' },
  { value: '1024x768', label: '1024×768（横图）' },
  { value: '768x1024', label: '768×1024（竖图）' },
  { value: '2K', label: '2K' },
  { value: '1K', label: '1K' },
];

type PlaygroundTab = 'chat' | 'image';

interface LocalMessage extends VisionChatMessage {
  id: string;
  imagePreviews?: string[];
}

interface ImageResult {
  id: string;
  prompt: string;
  size: string;
  urls: string[];
  referencePreviews?: string[];
}

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function VisionModelPlayground() {
  const [activeTab, setActiveTab] = useState<PlaygroundTab>('chat');
  const [config, setConfig] = useState<VisionChatConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);

  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [chatInput, setChatInput] = useState('');
  const [chatPendingImages, setChatPendingImages] = useState<string[]>([]);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [chatSending, setChatSending] = useState(false);

  const [imagePrompt, setImagePrompt] = useState('');
  const [imageSize, setImageSize] = useState('1024x1024');
  const [imageRefs, setImageRefs] = useState<string[]>([]);
  const [imageResults, setImageResults] = useState<ImageResult[]>([]);
  const [imageGenerating, setImageGenerating] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const chatFileInputRef = useRef<HTMLInputElement>(null);
  const imageFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void getVisionChatConfig()
      .then((res) => setConfig(res))
      .catch((err: unknown) => {
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          '无法加载配置（仅本地 development 环境可用）';
        setConfigError(String(detail));
      });
  }, []);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chatSending]);

  const pickChatImages = useCallback((files: FileList | null) => {
    if (!files?.length) return;
    const remaining = 3 - chatPendingImages.length;
    if (remaining <= 0) return;
    Array.from(files)
      .slice(0, remaining)
      .forEach((file) => {
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = reader.result;
          if (typeof dataUrl === 'string') {
            setChatPendingImages((prev) => (prev.length >= 3 ? prev : [...prev, dataUrl]));
          }
        };
        reader.readAsDataURL(file);
      });
  }, [chatPendingImages.length]);

  const pickImageRefs = useCallback((files: FileList | null) => {
    if (!files?.length) return;
    const remaining = 3 - imageRefs.length;
    if (remaining <= 0) return;
    Array.from(files)
      .slice(0, remaining)
      .forEach((file) => {
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = reader.result;
          if (typeof dataUrl === 'string') {
            setImageRefs((prev) => (prev.length >= 3 ? prev : [...prev, dataUrl]));
          }
        };
        reader.readAsDataURL(file);
      });
  }, [imageRefs.length]);

  const clearChat = () => {
    setMessages([]);
    setChatPendingImages([]);
    setError(null);
  };

  const clearImages = () => {
    setImageResults([]);
    setImageRefs([]);
    setError(null);
  };

  const handleChatSend = async () => {
    const text = chatInput.trim();
    if (!text || chatSending || configError) return;

    const userMessage: LocalMessage = {
      id: newId(),
      role: 'user',
      content: text,
      imagePreviews: chatPendingImages.length ? [...chatPendingImages] : undefined,
    };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setChatInput('');
    setError(null);
    setChatSending(true);

    const imagesForRequest = [...chatPendingImages];
    setChatPendingImages([]);

    try {
      const response = await sendVisionChat({
        messages: nextMessages.map(({ role, content }) => ({ role, content })),
        system_prompt: systemPrompt.trim() || undefined,
        image_urls: imagesForRequest,
        temperature,
        max_tokens: maxTokens,
      });
      setMessages((prev) => [
        ...prev,
        { id: newId(), role: 'assistant', content: response.content },
      ]);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        '请求失败';
      setError(String(detail));
    } finally {
      setChatSending(false);
    }
  };

  const handleImageGenerate = async () => {
    const prompt = imagePrompt.trim();
    if (!prompt || imageGenerating || configError) return;

    setError(null);
    setImageGenerating(true);
    const refs = [...imageRefs];

    try {
      const response = await generateVisionImage({
        prompt,
        size: imageSize,
        image_urls: refs,
      });
      setImageResults((prev) => [
        {
          id: newId(),
          prompt,
          size: imageSize,
          urls: response.image_urls,
          referencePreviews: refs.length ? refs : undefined,
        },
        ...prev,
      ]);
      setImagePrompt('');
      setImageRefs([]);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        '图像生成失败';
      setError(String(detail));
    } finally {
      setImageGenerating(false);
    }
  };

  const subtitle = config
    ? activeTab === 'chat'
      ? `${config.chat_model} · ${config.chat_api_url}`
      : `${config.image_model} · ${config.image_api_url}`
    : '本地 development 环境专用 playground';

  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col px-4 py-6 lg:px-8">
      <PageHeader
        title="Agnes 模型测试"
        subtitle={subtitle}
        actions={
          <button
            type="button"
            onClick={activeTab === 'chat' ? clearChat : clearImages}
            className="inline-flex items-center gap-2 rounded-lg border border-canvas-border px-3 py-2 text-sm text-ink-700 hover:bg-white"
          >
            <Trash2 className="h-4 w-4" />
            {activeTab === 'chat' ? '清空对话' : '清空结果'}
          </button>
        }
      />

      <div className="mb-4 flex gap-2 rounded-xl border border-canvas-border bg-white p-1 shadow-card">
        <button
          type="button"
          onClick={() => { setActiveTab('chat'); setError(null); }}
          className={`inline-flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
            activeTab === 'chat'
              ? 'bg-forge-600 text-white'
              : 'text-ink-600 hover:bg-canvas'
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          对话 · {config?.chat_model ?? 'agnes-2.5-flash'}
        </button>
        <button
          type="button"
          onClick={() => { setActiveTab('image'); setError(null); }}
          className={`inline-flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors ${
            activeTab === 'image'
              ? 'bg-forge-600 text-white'
              : 'text-ink-600 hover:bg-canvas'
          }`}
        >
          <ImageIcon className="h-4 w-4" />
          图像 · {config?.image_model ?? 'agnes-image-2.1-flash'}
        </button>
      </div>

      {configError ? (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {configError}
        </div>
      ) : null}

      {activeTab === 'chat' ? (
        <>
          <div className="mb-4 grid gap-4 rounded-xl border border-canvas-border bg-white p-4 shadow-card sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-ink-700">System Prompt</span>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-canvas-border px-3 py-2 text-sm text-ink-800 focus:border-forge-500 focus:outline-none focus:ring-1 focus:ring-forge-500"
              />
            </label>
            <div className="space-y-4 text-sm">
              <label className="block">
                <span className="mb-1 flex justify-between font-medium text-ink-700">
                  <span>Temperature</span>
                  <span className="text-ink-500">{temperature.toFixed(1)}</span>
                </span>
                <input
                  type="range"
                  min={0}
                  max={2}
                  step={0.1}
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  className="w-full"
                />
              </label>
              <label className="block">
                <span className="mb-1 flex justify-between font-medium text-ink-700">
                  <span>Max tokens</span>
                  <span className="text-ink-500">{maxTokens}</span>
                </span>
                <input
                  type="range"
                  min={256}
                  max={8192}
                  step={256}
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(Number(e.target.value))}
                  className="w-full"
                />
              </label>
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-canvas-border bg-white shadow-card">
            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              {messages.length === 0 ? (
                <div className="flex h-full min-h-[240px] flex-col items-center justify-center text-center text-ink-400">
                  <Bot className="mb-3 h-10 w-10" strokeWidth={1.5} />
                  <p className="text-sm">测试多模态对话与图像理解</p>
                  <p className="mt-1 text-xs">支持上传最多 3 张图片（随下一条用户消息发送）</p>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    {msg.role === 'assistant' ? (
                      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-forge-100 text-forge-700">
                        <Bot className="h-4 w-4" />
                      </div>
                    ) : null}
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                        msg.role === 'user'
                          ? 'bg-forge-600 text-white'
                          : 'bg-canvas text-ink-800 border border-canvas-border'
                      }`}
                    >
                      {msg.imagePreviews?.length ? (
                        <div className="mb-2 flex flex-wrap gap-2">
                          {msg.imagePreviews.map((src, i) => (
                            <img
                              key={`${msg.id}-ref-${i}`}
                              src={src}
                              alt={`用户上传 ${i + 1}`}
                              className="max-h-40 rounded-lg object-cover"
                            />
                          ))}
                        </div>
                      ) : null}
                      {msg.content}
                    </div>
                    {msg.role === 'user' ? (
                      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink-100 text-ink-600">
                        <User className="h-4 w-4" />
                      </div>
                    ) : null}
                  </div>
                ))
              )}
              {chatSending ? (
                <div className="flex items-center gap-2 text-sm text-ink-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  模型思考中…
                </div>
              ) : null}
              <div ref={chatBottomRef} />
            </div>

            {error && activeTab === 'chat' ? (
              <div className="border-t border-red-100 bg-red-50 px-4 py-2 text-sm text-red-700">
                {error}
              </div>
            ) : null}

            {chatPendingImages.length > 0 ? (
              <div className="flex flex-wrap gap-2 border-t border-canvas-border px-4 py-2">
                {chatPendingImages.map((url, index) => (
                  <div key={url} className="relative">
                    <img src={url} alt="" className="h-16 w-16 rounded-lg object-cover" />
                    <button
                      type="button"
                      onClick={() => setChatPendingImages((prev) => prev.filter((_, i) => i !== index))}
                      className="absolute -right-1 -top-1 rounded-full bg-ink-800 p-0.5 text-white"
                      aria-label="移除图片"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="flex items-end gap-2 border-t border-canvas-border p-4">
              <input
                ref={chatFileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => {
                  pickChatImages(e.target.files);
                  e.target.value = '';
                }}
              />
              <button
                type="button"
                onClick={() => chatFileInputRef.current?.click()}
                disabled={chatSending || chatPendingImages.length >= 3 || Boolean(configError)}
                className="rounded-lg border border-canvas-border p-2.5 text-ink-600 hover:bg-canvas disabled:opacity-50"
                title="添加图片"
              >
                <ImagePlus className="h-5 w-5" />
              </button>
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    void handleChatSend();
                  }
                }}
                placeholder="输入消息，Enter 发送，Shift+Enter 换行"
                rows={2}
                disabled={chatSending || Boolean(configError)}
                className="min-h-[44px] flex-1 resize-none rounded-xl border border-canvas-border px-3 py-2 text-sm focus:border-forge-500 focus:outline-none focus:ring-1 focus:ring-forge-500 disabled:bg-canvas"
              />
              <button
                type="button"
                onClick={() => void handleChatSend()}
                disabled={!chatInput.trim() || chatSending || Boolean(configError)}
                className="inline-flex items-center gap-2 rounded-xl bg-forge-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-forge-700 disabled:opacity-50"
              >
                {chatSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                发送
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-4">
          <div className="rounded-xl border border-canvas-border bg-white p-4 shadow-card">
            <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-ink-700">Prompt</span>
                <textarea
                  value={imagePrompt}
                  onChange={(e) => setImagePrompt(e.target.value)}
                  rows={3}
                  placeholder="描述要生成的图像，或说明如何编辑参考图…"
                  disabled={imageGenerating || Boolean(configError)}
                  className="w-full rounded-lg border border-canvas-border px-3 py-2 text-sm text-ink-800 focus:border-forge-500 focus:outline-none focus:ring-1 focus:ring-forge-500 disabled:bg-canvas"
                />
              </label>
              <div className="flex flex-col gap-3 sm:min-w-[180px]">
                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-ink-700">尺寸</span>
                  <select
                    value={imageSize}
                    onChange={(e) => setImageSize(e.target.value)}
                    disabled={imageGenerating || Boolean(configError)}
                    className="w-full rounded-lg border border-canvas-border px-3 py-2 text-sm focus:border-forge-500 focus:outline-none focus:ring-1 focus:ring-forge-500"
                  >
                    {IMAGE_SIZES.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => void handleImageGenerate()}
                  disabled={!imagePrompt.trim() || imageGenerating || Boolean(configError)}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-forge-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-forge-700 disabled:opacity-50"
                >
                  {imageGenerating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  生成图像
                </button>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <input
                ref={imageFileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => {
                  pickImageRefs(e.target.files);
                  e.target.value = '';
                }}
              />
              <button
                type="button"
                onClick={() => imageFileInputRef.current?.click()}
                disabled={imageGenerating || imageRefs.length >= 3 || Boolean(configError)}
                className="inline-flex items-center gap-2 rounded-lg border border-canvas-border px-3 py-2 text-sm text-ink-700 hover:bg-canvas disabled:opacity-50"
              >
                <ImagePlus className="h-4 w-4" />
                添加参考图（图生图，最多 3 张）
              </button>
              {imageRefs.map((url, index) => (
                <div key={url} className="relative">
                  <img src={url} alt="" className="h-16 w-16 rounded-lg object-cover" />
                  <button
                    type="button"
                    onClick={() => setImageRefs((prev) => prev.filter((_, i) => i !== index))}
                    className="absolute -right-1 -top-1 rounded-full bg-ink-800 p-0.5 text-white"
                    aria-label="移除参考图"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {error && activeTab === 'image' ? (
            <div className="rounded-xl border border-red-100 bg-red-50 px-4 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          <div className="flex-1 overflow-y-auto rounded-xl border border-canvas-border bg-white p-4 shadow-card">
            {imageResults.length === 0 ? (
              <div className="flex min-h-[280px] flex-col items-center justify-center text-center text-ink-400">
                <ImageIcon className="mb-3 h-10 w-10" strokeWidth={1.5} />
                <p className="text-sm">文生图或图生图测试 Agnes Image 2.1 Flash</p>
                <p className="mt-1 text-xs">上传参考图可进行图像编辑 / 风格变换</p>
              </div>
            ) : (
              <div className="space-y-6">
                {imageResults.map((item) => (
                  <div key={item.id} className="rounded-xl border border-canvas-border p-4">
                    <div className="mb-3 flex flex-wrap items-start gap-3 text-sm">
                      {item.referencePreviews?.length ? (
                        <div className="flex flex-wrap gap-2">
                          {item.referencePreviews.map((src, i) => (
                            <img
                              key={`${item.id}-ref-${i}`}
                              src={src}
                              alt={`参考图 ${i + 1}`}
                              className="h-16 w-16 rounded-lg object-cover"
                              title={`参考图 ${i + 1}`}
                            />
                          ))}
                        </div>
                      ) : null}
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-ink-800">{item.prompt}</p>
                        <p className="mt-1 text-xs text-ink-500">
                          {item.size}
                          {item.referencePreviews?.length
                            ? ` · ${item.referencePreviews.length} 张参考图`
                            : ''}
                        </p>
                      </div>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {item.urls.map((url) => (
                        <a
                          key={url}
                          href={url}
                          target="_blank"
                          rel="noreferrer"
                          className="block overflow-hidden rounded-lg border border-canvas-border bg-canvas"
                        >
                          <img src={url} alt={item.prompt} className="w-full object-contain" />
                        </a>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
