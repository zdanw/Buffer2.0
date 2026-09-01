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
  reference_product_image_ids?: string[];
  reference_scene_image_ids?: string[];
  compare_group_id?: string;
}

export interface ReferenceSelectionRequest {
  product_id: string;
  reference_count?: number;
  use_scene_reference?: boolean;
  image_size?: string;
}

export interface GenerationDiagnostics {
  state: 'planned' | 'running' | 'completed' | 'failed';
  run_id?: string | null;
  has_history?: boolean;
  summary: Array<{
    key: string;
    status: string;
    message_key: string;
    params?: Record<string, string | number>;
  }>;
  groups: Record<
    string,
    {
      status: string;
      items: Array<{ code: string; status: string; params?: Record<string, string | number> }>;
    }
  >;
  technical?: Record<string, unknown> | null;
}

export interface ReferenceSelectionResponse {
  reference_images: string[];
  reference_product_images: string[];
  reference_scene_images: string[];
  use_scene_reference: boolean;
  reference_product_image_ids?: string[];
  reference_scene_image_ids?: string[];
  reference_manifest?: Record<string, unknown>;
  generation_diagnostics?: GenerationDiagnostics;
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

export interface ReferenceDiagnostics {
  coverage?: string;
  reason?: string;
  diversity_applied?: boolean;
  selected_reference_id?: string | null;
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
  warning_code?: string;
  logo_mode?: string;
  reference_diagnostics?: ReferenceDiagnostics;
  generation_diagnostics?: GenerationDiagnostics;
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

export const persistCompareSelection = async (data: {
  compare_group_id: string;
  image_prompt_pipeline: 'legacy_scene' | 'vision_scene';
}): Promise<void> => {
  await axiosInstance.post('/generate/compare-selection/', data);
};

export const resolveReferenceSelection = async (
  data: ReferenceSelectionRequest
): Promise<ReferenceSelectionResponse> => {
  const response = await axiosInstance.post('/generate/reference-selection/', data);
  return response.data;
};

/** Status polls use a short timeout so hung Vercel→HF proxies do not starve other API calls. */
export const STATUS_POLL_REQUEST_TIMEOUT_MS = 12_000;

export const getGenerateStatus = async (taskId: string): Promise<GenerateStatus> => {
  const response = await axiosInstance.get(`/generate/status/${taskId}`, {
    timeout: STATUS_POLL_REQUEST_TIMEOUT_MS,
  });
  return response.data;
};

export const POLL_INTERVAL_MS = 1000;
export const POLL_INTERVAL_DEGRADED_MS = 3000;
export const POLL_INTERVAL_STALLED_MS = 5000;
/** Keep polling through ~2 minutes of consecutive transient errors. */
const MAX_CONSECUTIVE_POLL_ERRORS = 120;
/** ~5s of all polls failing — show connection warning in UI. */
export const POLL_WARN_CONSECUTIVE_FAILURES = 5;
/** ~20s of all polls failing — offer manual status refresh. */
export const POLL_STALL_CONSECUTIVE_FAILURES = 20;

export interface FetchGenerateStatusesResult {
  statuses: GenerateStatus[];
  failedTaskIds: string[];
  allSucceeded: boolean;
}

function isTransientPollError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return true;
  const e = error as { code?: string; message?: string; response?: { status?: number } };
  if (e.code === 'ECONNABORTED') return true;
  if (typeof e.message === 'string' && e.message.toLowerCase().includes('timeout')) return true;
  const status = e.response?.status;
  // 500 often means DB pool exhaustion during parallel compare runs — keep polling.
  return status === 500 || status === 502 || status === 503 || status === 504;
}

/** Poll each task independently; merge with previous snapshot when individual polls fail. */
export async function fetchGenerateStatuses(
  taskIds: string[],
  previousById?: Map<string, GenerateStatus>,
): Promise<FetchGenerateStatusesResult> {
  const results = await Promise.allSettled(taskIds.map((taskId) => getGenerateStatus(taskId)));
  const failedTaskIds: string[] = [];
  const statuses = taskIds.map((taskId, index) => {
    const result = results[index];
    if (result.status === 'fulfilled') {
      return result.value;
    }
    failedTaskIds.push(taskId);
    return (
      previousById?.get(taskId) ?? {
        task_id: taskId,
        status: 'PROGRESS',
        progress: 0,
        stage: 'queued',
      }
    );
  });
  return {
    statuses,
    failedTaskIds,
    allSucceeded: failedTaskIds.length === 0,
  };
}

export interface ProgressSegment {
  taskIds: string[];
  weight: number;
}

export interface GenerateProgressLayout {
  segments: ProgressSegment[];
  /** Compare-all needs 3 tasks before the batch can read as complete. */
  minTaskCount?: number;
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

  if (compareMode && generatingType === 'all') {
    if (taskIds.length < 3) {
      return {
        segments: [{ taskIds: [...taskIds], weight: 100 }],
        minTaskCount: 3,
      };
    }
    return {
      segments: [
        { taskIds: [taskIds[0]], weight: 25 },
        { taskIds: taskIds.slice(1, 3), weight: 75 },
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

  const layoutTaskIds = effectiveLayout.segments.flatMap((segment) => segment.taskIds);
  const statusById = new Map(statuses.map((item) => [item.task_id, item]));
  const batchRegistered =
    !effectiveLayout.minTaskCount || statuses.length >= effectiveLayout.minTaskCount;
  const allLayoutTasksSuccess =
    batchRegistered &&
    layoutTaskIds.length > 0 &&
    layoutTaskIds.every((id) => statusById.get(id)?.status === 'SUCCESS');

  if (allLayoutTasksSuccess) {
    return { progress: 100, stage: 'done', status: 'SUCCESS' };
  }
  if (
    batchRegistered &&
    layoutTaskIds.length > 0 &&
    layoutTaskIds.every((id) => {
      const status = statusById.get(id)?.status;
      return status === 'SUCCESS' || status === 'FAILURE';
    })
  ) {
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
  options?: { onProgress?: (status: GenerateStatus) => void },
): Promise<GenerateStatus> {
  let consecutiveErrors = 0;
  for (;;) {
    try {
      const status = await fetchStatus();
      consecutiveErrors = 0;
      options?.onProgress?.(status);
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
export const waitForGenerateTask = async (
  taskId: string,
  options?: { onProgress?: (status: GenerateStatus) => void },
): Promise<GenerateStatus> => pollUntilTerminal(() => getGenerateStatus(taskId), options);

/** Poll multiple tasks until all reach a terminal state. */
export const waitForGenerateTasks = async (
  taskIds: string[],
  options?: { onProgress?: (statuses: GenerateStatus[]) => void },
): Promise<GenerateStatus[]> => {
  let previousById = new Map<string, GenerateStatus>();
  let consecutiveErrors = 0;
  for (;;) {
    const results = await Promise.allSettled(taskIds.map((taskId) => getGenerateStatus(taskId)));
    const statuses = taskIds.map((taskId, index) => {
      const result = results[index];
      if (result.status === 'fulfilled') {
        return result.value;
      }
      return (
        previousById.get(taskId) ?? {
          task_id: taskId,
          status: 'PROGRESS',
          progress: 0,
          stage: 'queued',
        }
      );
    });
    previousById = new Map(statuses.map((item) => [item.task_id, item]));
    options?.onProgress?.(statuses);

    const allSucceeded = results.every((item) => item.status === 'fulfilled');
    if (allSucceeded) {
      consecutiveErrors = 0;
    } else {
      const firstFailure = results.find(
        (item): item is PromiseRejectedResult => item.status === 'rejected',
      );
      if (firstFailure && !isTransientPollError(firstFailure.reason)) {
        throw firstFailure.reason;
      }
      consecutiveErrors += 1;
      if (consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS && firstFailure) {
        throw firstFailure.reason;
      }
    }

    if (statuses.every((item) => item.status === 'SUCCESS' || item.status === 'FAILURE')) {
      return statuses;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
};
