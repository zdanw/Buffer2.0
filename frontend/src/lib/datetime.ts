/** 后端 DateTime 多为 UTC 无时区；按 UTC 解析后再转本地显示 */

export function parseServerDate(value: string | Date | null | undefined): Date | null {
  if (value == null) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  const raw = String(value).trim();
  if (!raw) return null;

  // 已带时区（Z 或 ±HH:MM）
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(raw)) {
    const d = new Date(raw);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // 无时区：按 UTC 处理（与 datetime.utcnow 一致）
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T');
  const d = new Date(`${normalized}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatServerDateTime(
  value: string | Date | null | undefined,
  options?: Intl.DateTimeFormatOptions
): string {
  const d = parseServerDate(value);
  if (!d) return '未知时间';
  return d.toLocaleString(
    'zh-CN',
    options ?? {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }
  );
}

export function formatServerDate(value: string | Date | null | undefined): string {
  const d = parseServerDate(value);
  if (!d) return '未知时间';
  return d.toLocaleDateString('zh-CN');
}
