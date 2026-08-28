import axiosInstance from './axiosInstance';

export interface GenerateRequest {
  product_id: string;
  platform: string;
  reference_count?: number;
  style_hint?: string;
  use_scene_reference?: boolean;
  use_vision_image_prompt?: boolean;
  realistic_placement?: boolean;
  image_provider_id?: string | null;
  image_model?: string | null;
  image_size?: string | null;
  image_provider_mode?: 'platform' | 'byok' | null;
  locale?: 'en' | 'zh';
  image_prompt_pipeline?: 'legacy_scene' | 'vision_scene';
  reference_product_images?: string[];
  reference_scene_images?: string[];
}

export interface ReferenceSelectionRequest {
  product_id: string;
  reference_count?: number;
  use_scene_reference?: boolean;
}

export interface ReferenceSelectionResponse {
  reference_images: string[];
  reference_product_images: string[];
  reference_scene_images: string[];
  use_scene_reference: boolean;
}

export interface GenerateResponse {
  task_id: string;
  status: string;
}

export interface DimensionInfo {
  scene: string;
  viewpoint: string;
  composition: string;
  style: string;
  quality: string;
  details: string;
  lighting: string;
}

export interface GenerateResult {
  success?: boolean;
  text?: string;
  image?: string;
  error?: string;
  dimensions?: DimensionInfo;
  image_prompt?: string;
  reference_product_images?: string[];
  reference_scene_images?: string[];
  warning?: string;
  logo_mode?: string;
}

export interface GenerateStatus {
  task_id: string;
  status: string;
  progress?: number;
  stage?: string | null;
  result?: GenerateResult;
}

export const generateContent = async (data: GenerateRequest): Promise<GenerateResponse> => {
  const response = await axiosInstance.post('/generate/', data);
  return response.data;
};

export const generateCopywriting = async (data: GenerateRequest): Promise<GenerateResponse> => {
  const response = await axiosInstance.post('/generate/copywriting/', data);
  return response.data;
};

export const generateImage = async (data: GenerateRequest): Promise<GenerateResponse> => {
  const response = await axiosInstance.post('/generate/image/', data);
  return response.data;
};

export const resolveReferenceSelection = async (
  data: ReferenceSelectionRequest
): Promise<ReferenceSelectionResponse> => {
  const response = await axiosInstance.post('/generate/reference-selection/', data);
  return response.data;
};

export const getGenerateStatus = async (taskId: string): Promise<GenerateStatus> => {
  const response = await axiosInstance.get(`/generate/status/${taskId}`);
  return response.data;
};

const POLL_INTERVAL_MS = 1000;
/** Keep polling through ~2 minutes of consecutive transient errors. */
const MAX_CONSECUTIVE_POLL_ERRORS = 120;

function isTransientPollError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return true;
  const e = error as { code?: string; message?: string; response?: { status?: number } };
  if (e.code === 'ECONNABORTED') return true;
  if (typeof e.message === 'string' && e.message.toLowerCase().includes('timeout')) return true;
  const status = e.response?.status;
  return status === 502 || status === 503 || status === 504;
}

export interface ProgressSegment {
  taskIds: string[];
  weight: number;
}

export interface GenerateProgressLayout {
  segments: ProgressSegment[];
}

/** Weighted layout so copy + image phases do not jump 100% → 50% when tasks merge. */
export function buildGenerateProgressLayout(
  taskIds: string[],
  options?: {
    generatingType?: 'all' | 'copywriting' | 'image' | null;
    compareMode?: boolean;
  },
): GenerateProgressLayout {
  const { generatingType = null, compareMode = false } = options ?? {};

  if (compareMode && generatingType === 'all' && taskIds.length >= 1) {
    return {
      segments: [
        { taskIds: [taskIds[0]], weight: 25 },
        {
          taskIds: taskIds.length >= 3 ? taskIds.slice(1, 3) : [],
          weight: 75,
        },
      ],
    };
  }

  if (compareMode && generatingType === 'image' && taskIds.length >= 2) {
    return {
      segments: [{ taskIds: taskIds.slice(0, 2), weight: 100 }],
    };
  }

  return { segments: [{ taskIds: [...taskIds], weight: 100 }] };
}

function segmentAverageProgress(statuses: GenerateStatus[], taskIds: string[]): number {
  if (taskIds.length === 0) return 0;
  const matched = statuses.filter((s) => taskIds.includes(s.task_id));
  if (matched.length === 0) return 0;
  const sum = matched.reduce((acc, s) => {
    if (s.status === 'SUCCESS') return acc + 100;
    if (s.status === 'FAILURE') return acc + 0;
    return acc + Math.max(0, Math.min(100, s.progress ?? 0));
  }, 0);
  return sum / matched.length;
}

function resolveAggregateStage(
  statuses: GenerateStatus[],
  layout: GenerateProgressLayout,
): string {
  for (const segment of layout.segments) {
    if (segment.taskIds.length === 0) continue;
    const matched = statuses.filter((s) => segment.taskIds.includes(s.task_id));
    if (matched.length === 0) continue;
    if (matched.every((s) => s.status === 'SUCCESS' || s.status === 'FAILURE')) {
      continue;
    }
    const inFlight = matched.filter(
      (s) => s.status === 'PENDING' || s.status === 'PROGRESS',
    );
    if (inFlight.length === 0) continue;
    const lagging = inFlight.reduce(
      (min, s) => ((s.progress ?? 0) < (min.progress ?? 0) ? s : min),
      inFlight[0],
    );
    const stage = lagging.stage ?? 'queued';
    return stage === 'done' ? 'finalizing' : stage;
  }
  return 'finalizing';
}

function weightedProgress(
  statuses: GenerateStatus[],
  layout: GenerateProgressLayout,
): number {
  let total = 0;
  for (const segment of layout.segments) {
    total += (segmentAverageProgress(statuses, segment.taskIds) / 100) * segment.weight;
  }
  return total;
}

/** Weighted progress across tasks; stage follows the earliest incomplete segment. */
export function aggregateGenerateProgress(
  statuses: GenerateStatus[],
  layout?: GenerateProgressLayout,
): Pick<GenerateStatus, 'progress' | 'stage' | 'status'> {
  if (statuses.length === 0) {
    return { progress: 0, stage: 'queued', status: 'PENDING' };
  }

  const effectiveLayout =
    layout ??
    buildGenerateProgressLayout(
      statuses.map((s) => s.task_id),
    );

  if (statuses.every((item) => item.status === 'SUCCESS')) {
    return { progress: 100, stage: 'done', status: 'SUCCESS' };
  }
  if (statuses.every((item) => item.status === 'SUCCESS' || item.status === 'FAILURE')) {
    return {
      progress: Math.round(weightedProgress(statuses, effectiveLayout)),
      stage: 'done',
      status: 'FAILURE',
    };
  }

  const progress = Math.min(99, Math.round(weightedProgress(statuses, effectiveLayout)));
  const stage = resolveAggregateStage(statuses, effectiveLayout);

  return {
    progress,
    stage,
    status: 'PROGRESS',
  };
}

async function pollUntilTerminal(
  fetchStatus: () => Promise<GenerateStatus>,
): Promise<GenerateStatus> {
  let consecutiveErrors = 0;
  for (;;) {
    try {
      const status = await fetchStatus();
      consecutiveErrors = 0;
      if (status.status === 'SUCCESS' || status.status === 'FAILURE') {
        return status;
      }
    } catch (error) {
      if (!isTransientPollError(error)) throw error;
      consecutiveErrors += 1;
      if (consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

/** Poll until SUCCESS or FAILURE; retries through transient network/proxy errors. */
export const waitForGenerateTask = async (taskId: string): Promise<GenerateStatus> =>
  pollUntilTerminal(() => getGenerateStatus(taskId));

/** Poll multiple tasks until all reach a terminal state. */
export const waitForGenerateTasks = async (taskIds: string[]): Promise<GenerateStatus[]> => {
  let consecutiveErrors = 0;
  for (;;) {
    try {
      const statuses = await Promise.all(taskIds.map(getGenerateStatus));
      consecutiveErrors = 0;
      if (statuses.every((item) => item.status === 'SUCCESS' || item.status === 'FAILURE')) {
        return statuses;
      }
    } catch (error) {
      if (!isTransientPollError(error)) throw error;
      consecutiveErrors += 1;
      if (consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
};