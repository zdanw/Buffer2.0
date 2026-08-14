import type { TranslationTree } from '../types';

export const sharedEn: TranslationTree = {
  validation: {
    required: '{{label}} is required',
    maxLen: '{{label}} must be at most {{max}} characters (current: {{current}})',
    maxLenSimple: '{{label}} must be at most {{max}} characters',
    minLen: '{{label}} must be at least {{min}} characters (current: {{current}})',
    emailFormat: '{{label}} format is invalid',
    cronLabel: 'CRON expression',
    cronParts: 'CRON must have 5 fields (minute hour day month weekday), e.g. 0 9 * * *',
    integer: '{{label}} must be an integer',
    range: '{{label}} must be between {{min}} and {{max}}',
    dimensionItemIdLabel: 'Dimension item ID',
    itemIdFormat: 'Dimension item ID may only contain letters, numbers, underscores, and hyphens',
  },
  pagination: {
    prev: 'Previous',
    next: 'Next',
    showing: 'Showing {{from}}–{{to}} of {{total}}',
    perPage: 'Per page:',
  },
  datetime: {
    unknown: 'Unknown time',
  },
  dimensionTypes: {
    scenes: 'Scene',
    lighting: 'Lighting',
    styles: 'Style',
    compositions: 'Composition',
    details: 'Detail',
    quality: 'Quality',
    viewpoints: 'Viewpoint',
  },
  dimensionTypeDescriptions: {
    scenes: 'Where the product appears — room, environment, or lifestyle setting.',
    lighting: 'Light direction, softness, and color temperature in the image.',
    styles: 'Overall visual mood — minimal, cozy, editorial, etc.',
    compositions: 'Camera framing and product placement in the frame.',
    details: 'Surface textures, props, and micro-elements around the product.',
    quality: 'Resolution, sharpness, and rendering fidelity hints.',
    viewpoints: 'Camera angle relative to the product — top-down, eye-level, etc.',
  },
  compat: {
    unrestricted: 'Fully compatible',
    none: 'None compatible',
    blocklist: 'Exclude {{count}}',
    count: '{{count}} item(s)',
    checkmark: '✔',
    self: '-',
    compatibleWith: 'Compatible {{label}}',
  },
  platforms: {
    instagram: 'Instagram',
    tiktok: 'TikTok',
    facebook: 'Facebook',
  },
  fields: {
    dimensionInfo: 'Dimension info',
    imagePrompt: 'Image prompt',
    selectProduct: 'Select product',
    selectProductPlaceholder: 'Choose a product',
    publishPlatforms: 'Publish platforms (multi-select)',
    imageModel: 'Image model',
    status: 'Status',
    actions: 'Actions',
    all: 'All',
    filter: 'Filter',
    filtering: 'Filtering…',
    noData: 'No data',
    copyContent: 'Copy',
    publishPlatformsLabel: 'Publish platforms',
  },
};

export const sharedZh: TranslationTree = {
  validation: {
    required: '{{label}}不能为空',
    maxLen: '{{label}}不能超过 {{max}} 个字符（当前 {{current}}）',
    maxLenSimple: '{{label}}不能超过 {{max}} 个字符',
    minLen: '{{label}}至少需要 {{min}} 个字符（当前 {{current}}）',
    emailFormat: '{{label}}格式不正确',
    cronLabel: 'CRON 表达式',
    cronParts: 'CRON 表达式须为 5 段（分 时 日 月 周），例如：0 9 * * *',
    integer: '{{label}}须为整数',
    range: '{{label}}须在 {{min}}–{{max}} 之间',
    dimensionItemIdLabel: '维度项ID',
    itemIdFormat: '维度项ID仅允许字母、数字、下划线和连字符',
  },
  pagination: {
    prev: '上一页',
    next: '下一页',
    showing: '显示第 {{from}} - {{to}} 条，共 {{total}} 条记录',
    perPage: '每页显示:',
  },
  datetime: {
    unknown: '未知时间',
  },
  dimensionTypes: {
    scenes: '场景',
    lighting: '光线',
    styles: '风格',
    compositions: '构图',
    details: '细节',
    quality: '画质',
    viewpoints: '视角',
  },
  dimensionTypeDescriptions: {
    scenes: '产品出现的环境与背景，如房间、场景或生活方式设定。',
    lighting: '画面光线方向、柔和度与色温。',
    styles: '整体视觉风格，如简约、温馨、杂志感等。',
    compositions: '镜头构图与产品在画面中的位置关系。',
    details: '材质纹理、道具与产品周围的细节元素。',
    quality: '分辨率、清晰度与渲染质量相关提示。',
    viewpoints: '相对产品的拍摄角度，如俯拍、平视等。',
  },
  compat: {
    unrestricted: '全部兼容',
    none: '都不兼容',
    blocklist: '排除{{count}}项',
    count: '{{count}}项',
    checkmark: '✔',
    self: '-',
    compatibleWith: '兼容{{label}}',
  },
  platforms: {
    instagram: 'Instagram',
    tiktok: 'TikTok',
    facebook: 'Facebook',
  },
  fields: {
    dimensionInfo: '维度信息',
    imagePrompt: '图像提示词',
    selectProduct: '选择产品',
    selectProductPlaceholder: '请选择产品',
    publishPlatforms: '发布平台 (多选)',
    imageModel: '图像模型',
    status: '状态',
    actions: '操作',
    all: '全部',
    filter: '筛选',
    filtering: '筛选中…',
    noData: '暂无数据',
    copyContent: '文案内容',
    publishPlatformsLabel: '发布平台',
  },
};

function mergeTrees(...trees: TranslationTree[]): TranslationTree {
  const result: TranslationTree = {};
  for (const tree of trees) {
    for (const [key, value] of Object.entries(tree)) {
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        result[key] = mergeTrees(
          (result[key] as TranslationTree) || {},
          value as TranslationTree,
        );
      } else {
        result[key] = value;
      }
    }
  }
  return result;
}

export function mergeLocale(...trees: TranslationTree[]): TranslationTree {
  return mergeTrees(...trees);
}
