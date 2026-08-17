import type { TranslationTree } from '../types';

export const placeholdersEn: TranslationTree = {
  placeholders: {
    brands: {
      name: 'e.g. Sunrise Co.',
      voice: 'Warm, confident, lifestyle-focused. Lead with benefits and keep the tone approachable.',
      audience: 'e.g. Urban professionals, ages 25–40, value design and quality',
      toneKeywords: 'e.g. modern, authentic, energetic, clean',
      hashtags: '#yourbrand, #lifestyle, #dailypost',
      wordsToAvoid: 'e.g. cheap, discount, exaggerated claim',
      logoFontRule: 'e.g. Use brand wordmark in rounded sans-serif; never distort logo',
      copySystemPrompt: 'Optional override. Example: Always lead with emotional benefit, then product feature.',
      imageSystemPrompt: 'Optional override. Example: Soft natural light, cohesive palette, minimal clutter.',
    },
    assets: {
      productName: 'e.g. Smart Night Light Pro',
      category: 'e.g. Home lighting',
      description: 'A Wi-Fi smart night light with app control, dimming, and warm-white presets.',
      sellingPoints: 'App scheduling, soft glow modes, energy efficient, 2-year warranty',
      brandVoice: 'Override only if this product needs a different tone than the brand kit.',
    },
    dimensions: {
      name: 'e.g. Soft morning lifestyle light',
      notes: 'e.g. Use for lifestyle scenes; avoid harsh shadows on product.',
    },
    tasks: {
      name: 'e.g. Daily Instagram — product highlights',
      cron: '0 9 * * 1-5',
      searchProducts: 'Search by product name…',
      referenceImageCount: 'e.g. 3',
      runCount: 'e.g. 1',
      generateImageCount: 'e.g. 2',
      generateCopyCount: 'e.g. 3',
    },
    studio: {
      selectProduct: 'e.g. Smart Night Light Pro',
    },
    imageModelPicker: {
      manualModel: 'e.g. qwen-image-2.0 or flux-1.1-pro',
      selectProviderFirst: 'Pick a provider above first',
      customSize: 'e.g. 1920x1080',
    },
    users: {
      username: 'e.g. content.ops',
      email: 'ops@yourcompany.com',
      emailFull: 'ops@yourcompany.com',
      passwordKeep: 'Leave blank to keep current password',
      autoPassword: 'Min. 6 characters',
    },
    login: {
      username: 'e.g. admin',
      password: 'Your password',
    },
    signup: {
      username: 'e.g. jane.chen',
      email: 'jane@company.com',
      password: 'At least 6 characters',
    },
    onboarding: {
      brandName: 'e.g. Sunrise Co.',
      brandVoice: 'Friendly expert voice for your audience…',
      productName: 'e.g. Smart Night Light',
    },
    imageProviders: {
      name: 'e.g. Production Doubao',
      baseUrl: 'https://api.openai.com/v1',
      apiKey: 'sk-…',
      defaultModel: 'e.g. qwen-image-2.0',
      modelId: 'e.g. qwen-image-edit-plus',
      modelNotes: 'Image-to-image variant; best for product scene compositing.',
      modelDoc: 'Resolution: 1024×1024. Supports reference images. Rate limit: 10 RPM.',
    },
    bufferAccounts: {
      name: 'e.g. Agency Buffer',
      token: 'Paste Buffer API token…',
    },
  },
};

export const placeholdersZh: TranslationTree = {
  placeholders: {
    brands: {
      name: '例如：晨光生活',
      voice: '温暖、自信、生活方式向。先写收益，语气亲切易懂。',
      audience: '例如：25–40 岁都市人群，注重设计与品质',
      toneKeywords: '例如：现代、真实、活力、简洁',
      hashtags: '#yourbrand, #生活方式, #每日更新',
      wordsToAvoid: '例如：便宜、打折、夸大功效',
      logoFontRule: '例如：使用品牌字标，圆润无衬线字体；不要拉伸 Logo',
      copySystemPrompt: '可选覆盖。示例：先写情感收益，再写产品功能。',
      imageSystemPrompt: '可选覆盖。示例：柔和自然光、统一色调、画面简洁。',
    },
    assets: {
      productName: '例如：智能小夜灯 Pro',
      category: '例如：家居照明',
      description: '支持 Wi-Fi 的智能小夜灯，可调光、App 控制与暖白预设。',
      sellingPoints: 'App 定时、柔光模式、节能、两年质保',
      brandVoice: '仅当本产品需要与品牌套件不同语气时填写。',
    },
    dimensions: {
      name: '例如：清晨柔和生活场景光',
      notes: '例如：用于生活场景图；避免产品上出现硬阴影。',
    },
    tasks: {
      name: '例如：每日 Instagram — 产品亮点',
      cron: '0 9 * * 1-5',
      searchProducts: '按产品名搜索…',
      referenceImageCount: '例如：3',
      runCount: '例如：1',
      generateImageCount: '例如：2',
      generateCopyCount: '例如：3',
    },
    studio: {
      selectProduct: '例如：智能小夜灯 Pro',
    },
    imageModelPicker: {
      manualModel: '例如：qwen-image-2.0 或 flux-1.1-pro',
      selectProviderFirst: '请先选择上方的服务商',
      customSize: '例如：1920x1080',
    },
    users: {
      username: '例如：content.ops',
      email: 'ops@company.com',
      emailFull: 'ops@company.com',
      passwordKeep: '留空表示不修改密码',
      autoPassword: '至少 6 位字符',
    },
    login: {
      username: '例如：admin',
      password: '请输入密码',
    },
    signup: {
      username: '例如：zhang.san',
      email: 'zhang@company.com',
      password: '至少 6 位字符',
    },
    onboarding: {
      brandName: '例如：晨光生活',
      brandVoice: '面向受众的亲切专家语气…',
      productName: '例如：智能小夜灯',
    },
    imageProviders: {
      name: '例如：生产环境豆包',
      baseUrl: 'https://api.openai.com/v1',
      apiKey: 'sk-…',
      defaultModel: '例如：qwen-image-2.0',
      modelId: '例如：qwen-image-edit-plus',
      modelNotes: '图生图模型；适合产品场景合成。',
      modelDoc: '分辨率 1024×1024，支持参考图，限速 10 RPM。',
    },
    bufferAccounts: {
      name: '例如：代理商 Buffer',
      token: '粘贴 Buffer API Token…',
    },
  },
};
