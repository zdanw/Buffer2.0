import type { TranslationTree } from '../types';

export const guidesEn: TranslationTree = {
  help: {
    title: 'Help Center',
    subtitle: 'Guides, onboarding, and answers for PulseForge',
    searchPlaceholder: 'Search guides…',
    backToApp: 'Back to app',
    openArticle: 'Read guide',
    screenshotAlt: 'Screenshot: {{page}}',
    screenshotCaption: 'PulseForge — {{page}}',
    tableOfContents: 'On this page',
    stepsTitle: 'Steps',
    tipsTitle: 'Tips',
    faqTitle: 'Frequently asked questions',
    relatedTitle: 'Related guides',
    noResults: 'No guides match your search.',
    publicIndexHint:
      'These guides are public and indexable. Use them to learn PulseForge before or after signing up.',
    publicFaqHint: 'Answers to common questions about publishing, credits, Buffer, and generation.',
    openFaq: 'View all FAQ',
    backToIndex: 'All guides',
    openPublicDocs: 'Public docs (indexable)',
    sections: {
      gettingStarted: 'Getting started',
      contentSetup: 'Content setup',
      createAndPublish: 'Create & publish',
      integrations: 'Integrations & billing',
    },
    articles: {
      quickStart: {
        title: 'Quick start — your first post in 5 minutes',
        summary:
          'Sign up, set up a brand and product, generate in Studio, then publish manually or on a schedule.',
        body: {
          '1':
            'PulseForge turns your product photos and brand rules into platform-ready social posts. This guide walks you through the shortest path from a blank account to a published (or queued) post.',
          '2':
            'You can skip detailed brand setup at first — the onboarding wizard and Generic brand let you experiment immediately. Come back to Brand kits when you want consistent voice across many products.',
        },
        steps: {
          '1': 'Create an account at Sign up. You receive trial image credits to test generation.',
          '2': 'On first login, complete the onboarding wizard (or skip it). Create a brand name + voice, or choose Generic.',
          '3': 'Add a product under Products with at least one product image. Scene/lifestyle photos improve Studio results.',
          '4': 'Open Studio, pick your product and target platforms (Instagram, Facebook, TikTok, etc.).',
          '5': 'Click Generate both to create caption + image. Preview in the phone mockup on the right.',
          '6': 'Publish now via Buffer, or Save to Review if you use manual approval.',
          '7': 'Optional: create an Automation (CRON task) to generate on a schedule — auto-publish or send drafts to Review.',
        },
        tips: {
          '1': 'Watch the Getting started checklist in the bottom-right corner — it links directly to each step.',
          '2': 'Complete brand + product + first generation to earn bonus free image credits.',
        },
      },
      onboarding: {
        title: 'Onboarding wizard & checklist',
        summary:
          'What happens when you first sign in, how to use the wizard, and how the floating checklist tracks your progress.',
        body: {
          '1':
            'After your first login, PulseForge shows a short wizard. You can skip it anytime — your account is fully usable without finishing.',
          '2':
            'A floating Getting started checklist stays in the bottom-right until you complete all core steps. Click any incomplete step to jump to the right page.',
        },
        steps: {
          '1': 'Welcome — overview of the 5-minute path. Click Get started.',
          '2': 'Quick brand — enter a brand name and voice, or check “No specific brand (Generic)”.',
          '3': 'Quick product — name your product and upload at least one image.',
          '4': 'Done — click Go to Studio to generate your first post.',
        },
        tips: {
          '1': 'The checklist also lists optional setup: Visual styles, Automations, and Image models.',
        },
      },
      brandKits: {
        title: 'Brand kits',
        summary:
          'Define voice, audience, hashtags, and Buffer binding once — every product under the brand inherits these rules.',
        body: {
          '1':
            'Brand kits are the single source of truth for how PulseForge writes copy and handles logos in images. Products inherit brand voice unless you override them per product.',
          '2':
            'Bind one Buffer account per brand so publishes route to the correct social profiles.',
          '3':
            'Logo rules control whether generated images preserve packaging logos, omit them, or composite your brand logo on export.',
        },
        tips: {
          '1': 'Use the brand selector bar at the top to filter Studio, Automations, and Calendar by brand.',
        },
      },
      products: {
        title: 'Products & reference images',
        summary:
          'Add products, upload product and scene photos, configure visual setup, and link visual styles.',
        body: {
          '1':
            'Each product needs a name, category, and at least one reference image before Studio can generate. Product images show the item clearly; scene images show it in real environments (nursery, desk, kitchen, etc.).',
          '2':
            'Visual setup tells PulseForge what kind of item this is (physical product, software, service, etc.) so image generation stays realistic.',
          '3':
            'Mark a preferred reference image when you have several — Studio uses it first. You can inherit brand voice or override tone per product.',
        },
        tips: {
          '1': 'Upload 2–4 product angles for better color and shape match in generated images.',
          '2': 'Scene photos power the Scene reference toggle in Studio for lifestyle-style outputs.',
        },
      },
      visualStyles: {
        title: 'Visual styles',
        summary:
          'Shared presets for scenes, lighting, composition, and mood — applied when generating images.',
        body: {
          '1':
            'Visual styles are your catalog of image “looks”: cozy nursery, golden hour, minimalist white, etc. They are shared across your brands and filtered by product type.',
          '2':
            'On first run, PulseForge seeds general presets automatically. Import Baby or other vertical packs if you need industry-specific options.',
          '3':
            'Link styles to products in the Products page, or let Studio pick from compatible presets for the product category.',
        },
        tips: {
          '1': 'Combine scene reference photos with visual styles for the most photo-specific results.',
        },
      },
      studio: {
        title: 'Studio — generate & preview',
        summary:
          'One-off generation with phone previews for Instagram, TikTok, and Facebook before anything goes live.',
        body: {
          '1':
            'Studio is where you manually generate copy, images, or both. Select a product and platforms, tune image options, then preview in device frames.',
          '2':
            'Advanced controls: Scene reference (use lifestyle photos), Vision prompt (AI reads your refs), Realistic placement, and pipeline comparison.',
          '3':
            'Publish sends to Buffer immediately. Save to Review creates a draft for the Review queue when you want human approval first.',
        },
        tips: {
          '1': 'Hover the (?) icons next to controls for detailed examples of each option.',
          '2': 'Copy only is useful when you already have a photo and need fresh hooks per platform.',
        },
      },
      automations: {
        title: 'Automations (scheduled tasks)',
        summary:
          'CRON-scheduled generation — auto-publish to Buffer or send drafts to Review.',
        body: {
          '1':
            'Automations run on a schedule you define with a CRON expression (minute hour day month weekday). Each run can target one or many products.',
          '2':
            'Auto publish: generates content and sends it to Buffer without human review. Manual publish: saves drafts to the Review queue.',
          '3':
            'Configure platforms, images per run, copy variants, scene reference, vision prompt, and optional email notification on publish.',
        },
        tips: {
          '1': 'Start with manual mode until you trust output quality, then switch tasks to auto publish.',
        },
      },
      review: {
        title: 'Review queue',
        summary:
          'Pick the best image and copy variant, ensure CDN hosting, then publish or discard.',
        body: {
          '1':
            'Drafts appear here from manual Automations or when you Save to Review from Studio. Select a draft on the left to review variants on the right.',
          '2':
            'Choose one image and one copy variant, select target platforms, then Publish. Images marked “Not on CDN” must be re-uploaded before publishing — temporary links can expire.',
          '3':
            'Discard removes a draft permanently. Published items show up on the Calendar.',
        },
        tips: {
          '1': 'If you see a CDN banner, click Re-upload on affected images before publishing.',
        },
      },
      calendar: {
        title: 'Publish calendar',
        summary:
          'See scheduled automations and execution history day by day.',
        body: {
          '1':
            'The calendar shows when automations are scheduled to run and what actually executed. Use it to verify auto-publish results or find drafts that need Review.',
          '2':
            'Click entries to see details. Manual-mode runs that produced drafts link to the Review queue.',
        },
      },
      buffer: {
        title: 'Connect Buffer for publishing',
        summary:
          'Add your Buffer API token, bind it to a brand, then publish from Studio, Review, or Automations.',
        body: {
          '1':
            'PulseForge publishes through Buffer — you need a Buffer account with connected social profiles. Each brand kit binds to exactly one Buffer token.',
        },
        steps: {
          '1': 'In Buffer, go to Account → Developers → Create an app or use an existing access token.',
          '2': 'In PulseForge, open Buffer accounts under Settings and paste your API token. Test the connection.',
          '3': 'Open Brand kits, edit your brand, and select the Buffer account to bind.',
          '4': 'Publish from Studio, Review, or enable auto publish on an Automation.',
        },
      },
      imageModels: {
        title: 'Image models & credits',
        summary:
          'Platform credits vs bring-your-own-key (BYOK) image providers.',
        body: {
          '1':
            'PulseForge includes platform image credits (shown in the top bar). Each image generation consumes one credit unless you configure your own provider.',
          '2':
            'Under Image Models, add providers (e.g. Doubao) with your API key. Set one as default for your account. Automations can override the model per task.',
          '3':
            'Admins configure system-wide providers under Platform Image (admin only).',
        },
        tips: {
          '1': 'Pipeline comparison in Studio uses 2 credits (one per pipeline).',
        },
      },
      billing: {
        title: 'Account & billing',
        summary:
          'Manage your profile, subscription, image credits, and invoices.',
        body: {
          '1':
            'The Account page shows your email, subscription tier, remaining image credits, and Stripe billing history.',
          '2':
            'Upgrade plans (Basic, Pro, Super) add monthly image credits. You can also complete onboarding to earn bonus credits.',
        },
        tips: {
          '1': 'If credits run out, add a BYOK image provider or upgrade your plan.',
        },
      },
    },
    faq: {
      whatIsPulseforge: {
        q: 'What is PulseForge?',
        a: 'PulseForge is a multi-brand social content platform. You define brand voice and product assets, then AI generates platform-specific copy and images. Content can auto-publish via Buffer or go through a Review queue first.',
      },
      autoVsManual: {
        q: 'What is the difference between auto and manual publish?',
        a: 'Auto publish generates and sends posts to Buffer on schedule — no human step. Manual publish still runs on schedule but saves drafts to Review so you pick the best image and copy before publishing.',
      },
      bufferToken: {
        q: 'Why do I need a Buffer token?',
        a: 'PulseForge does not post directly to Instagram or Facebook. Buffer handles scheduling and delivery to connected social accounts. One Buffer token is bound per brand kit.',
      },
      credits: {
        q: 'How do image credits work?',
        a: 'Each image generation uses one platform credit by default. Signup and onboarding grants include free credits. Subscribe for monthly packs, or add your own image provider API key under Image Models.',
      },
      cdnPublish: {
        q: 'Why must images be on CDN before publishing?',
        a: 'Generated images may start on temporary URLs. Buffer needs stable public URLs. PulseForge re-uploads to GitHub CDN; Review shows “Not on CDN” until that completes.',
      },
      generationFails: {
        q: 'Why did generation fail?',
        a: 'Common causes: no product reference images, exhausted credits, backend/API unreachable (check the connection banner), or image provider misconfiguration. Ensure the product has at least one image and credits remain.',
      },
      cronFormat: {
        q: 'How do I write a CRON expression?',
        a: 'Use five fields: minute hour day month weekday. Example: `0 9 * * *` runs daily at 09:00. The Automations form shows a hint and validates your expression.',
      },
      genericBrand: {
        q: 'What is the Generic brand?',
        a: 'Generic is a fallback when you do not need brand-specific voice rules. Products without a brand kit still generate; voice is neutral. Create a named brand kit when you want consistent tone and Buffer binding.',
      },
      logoInImages: {
        q: 'How are logos handled in generated images?',
        a: 'Per brand: Preserve keeps logos visible on packaging in reference photos; Omit removes logos; Composite adds your brand logo on export. Configure under Brand kits.',
      },
      languages: {
        q: 'What language is generated content in?',
        a: 'Social copy is generated in English by default (tuned per platform). Image prompts use Chinese internally for the image model. Switch the app UI between English and 中文 with the language toggle in the sidebar.',
      },
    },
  },
};

export const guidesZh: TranslationTree = {
  help: {
    title: '帮助中心',
    subtitle: 'PulseForge 使用指南、入门说明与常见问题',
    searchPlaceholder: '搜索指南…',
    backToApp: '返回应用',
    openArticle: '阅读指南',
    screenshotAlt: '截图：{{page}}',
    screenshotCaption: 'PulseForge — {{page}}',
    tableOfContents: '本页目录',
    stepsTitle: '操作步骤',
    tipsTitle: '提示',
    faqTitle: '常见问题',
    relatedTitle: '相关指南',
    noResults: '没有匹配的指南。',
    publicIndexHint: '本指南对外公开，可供搜索引擎与 AI 索引。注册前后均可阅读。',
    publicFaqHint: '关于发布、额度、Buffer 与生成失败的常见问题。',
    openFaq: '查看全部常见问题',
    backToIndex: '全部指南',
    openPublicDocs: '公开文档（可被索引）',
    sections: {
      gettingStarted: '快速入门',
      contentSetup: '内容配置',
      createAndPublish: '创作与发布',
      integrations: '集成与计费',
    },
    articles: {
      quickStart: {
        title: '快速上手 — 5 分钟发出第一条内容',
        summary: '注册账号、配置品牌与产品、在 Studio 生成，再手动发布或定时自动化。',
        body: {
          '1': 'PulseForge 根据产品照片与品牌规则生成各平台可用的社媒文案与配图。本指南是从空账号到发布（或进入审核队列）的最短路径。',
          '2': '初期可跳过详尽品牌配置 — 入门向导与「通用」品牌即可马上试生成。需要多产品统一语气时再完善品牌套件。',
        },
        steps: {
          '1': '在注册页创建账号，即可获得试用出图额度。',
          '2': '首次登录完成入门向导（可跳过）：填写品牌名与调性，或选择「无特定品牌（通用）」。',
          '3': '在「产品」中添加产品并上传至少一张产品图；场景/生活方式图可提升 Studio 效果。',
          '4': '打开 Studio，选择产品与目标平台（Instagram、Facebook、TikTok 等）。',
          '5': '点击「同时生成」得到文案与图像，右侧手机框预览效果。',
          '6': '通过 Buffer 立即发布，或「保存到审核」走人工把关。',
          '7': '可选：在「自动化」中配置 CRON 定时任务 — 自动发布或生成草稿到审核队列。',
        },
        tips: {
          '1': '留意右下角「入门指南」浮层，可一键跳转到对应步骤。',
          '2': '完成品牌 + 产品 + 首次生成可获得额外免费出图额度。',
        },
      },
      onboarding: {
        title: '入门向导与清单',
        summary: '首次登录流程、向导各步骤，以及右下角清单如何跟踪进度。',
        body: {
          '1': '首次登录后会弹出简短向导，可随时跳过，不影响正常使用。',
          '2': '右下角「入门指南」清单在完成全部核心步骤前会一直显示，点击未完成项可直达对应页面。',
        },
        steps: {
          '1': '欢迎页 — 了解 5 分钟路径，点击「开始使用」。',
          '2': '快速品牌 — 输入品牌名与调性，或勾选「无特定品牌（通用）」。',
          '3': '快速产品 — 填写产品名并上传至少一张图片。',
          '4': '完成 — 点击「前往 Studio」生成第一条内容。',
        },
        tips: {
          '1': '清单中还列出可选配置：视觉风格、自动化、图像模型。',
        },
      },
      brandKits: {
        title: '品牌套件',
        summary: '一次配置语气、受众、标签与 Buffer 绑定，旗下产品自动继承。',
        body: {
          '1': '品牌套件决定文案风格与图像中的 Logo 处理方式；产品默认继承品牌调性，也可单独覆盖。',
          '2': '每个品牌绑定一个 Buffer 账户，发布时走对应社媒主页。',
          '3': 'Logo 规则：保留包装上的标识、生成时不含 Logo、或在导出时叠加品牌 Logo。',
        },
        tips: {
          '1': '使用顶部品牌选择条在 Studio、自动化与日历中按品牌筛选。',
        },
      },
      products: {
        title: '产品与参考图',
        summary: '添加产品、上传产品与场景图、配置视觉设定并关联视觉风格。',
        body: {
          '1': '每个产品需有名称、分类和至少一张参考图才能生成。产品图展示商品本身；场景图展示真实使用环境（婴儿房、书桌等）。',
          '2': '「视觉设定」说明产品类型（实体商品、软件、服务等），使出图更贴近真实。',
          '3': '多张参考图时可标记「首选」；可继承品牌语气或按产品单独设置。',
        },
        tips: {
          '1': '上传 2–4 张不同角度产品图，颜色与外形还原更好。',
          '2': '场景图配合 Studio 中的「场景参考」可生成生活方式风格画面。',
        },
      },
      visualStyles: {
        title: '视觉风格',
        summary: '场景、光线、构图等图像预设，在生成时组合使用。',
        body: {
          '1': '视觉风格是图像「观感」目录：温馨婴儿房、黄金时刻、极简白底等，在品牌间共享，并按产品类型筛选。',
          '2': '首次启动会自动加载通用预设；可按需导入母婴等行业包。',
          '3': '在产品页关联风格，或由 Studio 按分类自动匹配兼容预设。',
        },
        tips: {
          '1': '场景参考图 + 视觉风格组合，出图最贴参考照片。',
        },
      },
      studio: {
        title: 'Studio — 生成与预览',
        summary: '单次生成，并在 Instagram、TikTok、Facebook 手机框中预览后再发布。',
        body: {
          '1': 'Studio 用于手动生成文案、图像或二者。选择产品与平台，调整图像选项后在设备框中预览。',
          '2': '高级选项：场景参考、视觉写 Prompt、真实摆放、双链路对比等。',
          '3': '「发布」经 Buffer 立即发出；「保存到审核」进入审核队列人工挑选。',
        },
        tips: {
          '1': '控件旁的 (?) 图标有详细说明与示例。',
          '2': '「仅文案」适合已有配图、只需各平台不同文案时使用。',
        },
      },
      automations: {
        title: '自动化（定时任务）',
        summary: '按 CRON 定时生成 — 自动发布到 Buffer 或草稿进入审核。',
        body: {
          '1': '用 CRON 表达式（分 时 日 月 周）设定执行时间，每次可覆盖一个或多个产品。',
          '2': '自动发布：生成后直接发到 Buffer；手动发布：草稿进入「审核」队列。',
          '3': '可配置平台、每轮图片/文案数量、场景参考、视觉 Prompt、发布后邮件通知等。',
        },
        tips: {
          '1': '建议先用人工模式验证质量，再改为自动发布。',
        },
      },
      review: {
        title: '审核队列',
        summary: '挑选最佳图片与文案，确保 CDN 托管后发布或丢弃。',
        body: {
          '1': '来自手动自动化或 Studio「保存到审核」的草稿列在左侧，右侧查看各版本。',
          '2': '各选一张图、一条文案并选平台后发布。标记「未上传 CDN」的需先重新上传 — 临时链接可能失效。',
          '3': '丢弃不可恢复；已发布记录出现在发布日历。',
        },
        tips: {
          '1': '出现 CDN 提示时，对受影响图片点击「重新上传」后再发布。',
        },
      },
      calendar: {
        title: '发布日历',
        summary: '按日查看计划任务与执行记录。',
        body: {
          '1': '日历展示自动化计划与实际执行，用于核对自动发布或查找待审核草稿。',
          '2': '点击条目查看详情；人工模式产生的草稿可跳转审核队列。',
        },
      },
      buffer: {
        title: '连接 Buffer 发布',
        summary: '添加 Buffer API 令牌、绑定品牌，即可从 Studio、审核或自动化发布。',
        body: {
          '1': 'PulseForge 通过 Buffer 发布到已连接的社媒账号；每个品牌套件绑定一个 Buffer 令牌。',
        },
        steps: {
          '1': '在 Buffer：账户 → 开发者 → 创建应用或获取访问令牌。',
          '2': '在 PulseForge「Buffer 账户」中粘贴令牌并测试连接。',
          '3': '在「品牌」中编辑品牌并选择要绑定的 Buffer 账户。',
          '4': '从 Studio、审核发布，或为自动化开启自动发布。',
        },
      },
      imageModels: {
        title: '图像模型与额度',
        summary: '平台出图额度与自带 API Key（BYOK）图像服务。',
        body: {
          '1': '顶部栏显示平台出图额度；默认每次图像生成消耗 1 次额度。',
          '2': '在「图像模型」中添加服务商（如豆包）与 API Key，可设默认；自动化任务可单独指定模型。',
          '3': '管理员在「平台图像」配置全站服务商。',
        },
        tips: {
          '1': 'Studio 双链路对比每次消耗 2 次出图额度。',
        },
      },
      billing: {
        title: '账户与计费',
        summary: '管理资料、订阅、出图额度与账单。',
        body: {
          '1': '「个人信息」页显示邮箱、订阅档位、剩余额度与 Stripe 账单记录。',
          '2': '升级 Basic / Pro / Super 获得月度额度；完成入门指南也可获得奖励额度。',
        },
        tips: {
          '1': '额度用尽时可配置 BYOK 图像服务或升级套餐。',
        },
      },
    },
    faq: {
      whatIsPulseforge: {
        q: 'PulseForge 是什么？',
        a: '多品牌社媒内容平台：配置品牌语气与产品素材后，AI 生成各平台文案与配图，可经 Buffer 自动发布或先进入审核队列。',
      },
      autoVsManual: {
        q: '自动发布和手动发布有什么区别？',
        a: '自动发布按计划在生成后直接发到 Buffer；手动发布同样定时生成，但草稿进入「审核」，由你挑选后再发布。',
      },
      bufferToken: {
        q: '为什么需要 Buffer 令牌？',
        a: 'PulseForge 不直接对接 Instagram/Facebook API，由 Buffer 负责排队与投递；每个品牌绑定一个 Buffer 令牌。',
      },
      credits: {
        q: '出图额度怎么用？',
        a: '默认每次图像生成消耗 1 次平台额度。注册与入门有赠送；可订阅月包，或在「图像模型」配置自己的 API Key。',
      },
      cdnPublish: {
        q: '为什么发布前图像要在 CDN 上？',
        a: '生成图可能先是临时链接，Buffer 需要稳定公网 URL。PulseForge 会同步到 GitHub CDN；审核页显示「未上传 CDN」时需先处理。',
      },
      generationFails: {
        q: '生成失败常见原因？',
        a: '缺少产品参考图、额度不足、后端不可达（看顶部连接提示）、或图像服务商配置错误。请确保产品有图且仍有额度。',
      },
      cronFormat: {
        q: 'CRON 表达式怎么写？',
        a: '五个字段：分 时 日 月 周。例：`0 9 * * *` 表示每天 09:00。自动化表单有格式提示与校验。',
      },
      genericBrand: {
        q: '「通用」品牌是什么？',
        a: '不需要专属品牌规则时使用，语气偏中性。需要统一调性与 Buffer 绑定时请创建具名品牌套件。',
      },
      logoInImages: {
        q: '生成图中的 Logo 如何处理？',
        a: '按品牌设置：保留参考图包装标识、生成时不含 Logo、或导出时叠加品牌 Logo。在品牌套件中配置。',
      },
      languages: {
        q: '生成内容用什么语言？',
        a: '社媒文案默认英文（按平台调整）；图像 Prompt 内部使用中文。应用界面可在侧栏切换 English / 中文。',
      },
    },
  },
};
