/** 与后端 SQLAlchemy 字段长度对齐的前端校验 */

export const LIMITS = {
  productName: 255,
  category: 100,
  brandVoice: 100,
  sellingPointsJoined: 500,
  description: 5000,
  taskName: 255,
  cron: 100,
  dimensionItemId: 100,
  dimensionName: 500,
  productType: 100,
  username: { min: 3, max: 50 },
  password: { min: 6, max: 128 },
  email: 100,
  referenceImageCount: { min: 1, max: 10 },
  runCount: { min: 1, max: 5 },
  generateImageCount: { min: 1, max: 10 },
  generateCopyCount: { min: 1, max: 10 },
} as const;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ITEM_ID_RE = /^[a-zA-Z0-9_-]+$/;

export function required(label: string, value: string | undefined | null): string | null {
  if (value == null || !String(value).trim()) return `${label}不能为空`;
  return null;
}

export function maxLen(label: string, value: string | undefined | null, max: number): string | null {
  if (value == null || value === '') return null;
  if (value.length > max) return `${label}不能超过 ${max} 个字符（当前 ${value.length}）`;
  return null;
}

export function minLen(label: string, value: string | undefined | null, min: number): string | null {
  if (value == null || value === '') return null;
  if (value.length < min) return `${label}至少需要 ${min} 个字符（当前 ${value.length}）`;
  return null;
}

export function emailFormat(label: string, value: string | undefined | null, optional = false): string | null {
  if (value == null || !value.trim()) return optional ? null : `${label}不能为空`;
  if (value.length > LIMITS.email) return `${label}不能超过 ${LIMITS.email} 个字符`;
  if (!EMAIL_RE.test(value.trim())) return `${label}格式不正确`;
  return null;
}

export function cronFormat(value: string | undefined | null): string | null {
  const err = required('CRON 表达式', value) || maxLen('CRON 表达式', value, LIMITS.cron);
  if (err) return err;
  const parts = value!.trim().split(/\s+/);
  if (parts.length !== 5) return 'CRON 表达式须为 5 段（分 时 日 月 周），例如：0 9 * * *';
  return null;
}

export function intInRange(label: string, value: number | undefined | null, min: number, max: number): string | null {
  if (value == null || !Number.isFinite(value) || !Number.isInteger(value)) return `${label}须为整数`;
  if (value < min || value > max) return `${label}须在 ${min}–${max} 之间`;
  return null;
}

export function itemIdFormat(value: string | undefined | null): string | null {
  const err = required('维度项ID', value) || maxLen('维度项ID', value, LIMITS.dimensionItemId);
  if (err) return err;
  if (!ITEM_ID_RE.test(value!.trim())) return '维度项ID仅允许字母、数字、下划线和连字符';
  return null;
}

/** 有错误则 alert 并返回 true（应中止提交） */
export function alertValidationErrors(errors: Array<string | null | undefined>): boolean {
  const messages = errors.filter((e): e is string => Boolean(e));
  if (messages.length === 0) return false;
  alert(messages.join('\n'));
  return true;
}
