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

/** Average progress across tasks; stage follows the slowest in-flight task. */
export function aggregateGenerateProgress(
  statuses: GenerateStatus[],
): Pick<GenerateStatus, 'progress' | 'stage' | 'status'> {
  if (statuses.length === 0) {
    return { progress: 0, stage: 'queued', status: 'PENDING' };
  }

  const progress = Math.round(
    statuses.reduce((sum, item) => sum + (item.progress ?? 0), 0) / statuses.length,
  );

  if (statuses.every((item) => item.status === 'SUCCESS')) {
    return { progress: 100, stage: 'done', status: 'SUCCESS' };
  }
  if (statuses.every((item) => item.status === 'SUCCESS' || item.status === 'FAILURE')) {
    return { progress, stage: 'done', status: 'FAILURE' };
  }

  const inFlight = statuses.filter(
    (item) => item.status === 'PENDING' || item.status === 'PROGRESS',
  );
  const lagging = inFlight.reduce(
    (min, item) => ((item.progress ?? 0) < (min.progress ?? 0) ? item : min),
    inFlight[0],
  );

  return {
    progress,
    stage: lagging?.stage ?? 'queued',
    status: 'PROGRESS',
  };
}

/** Poll until SUCCESS or FAILURE. */
export const waitForGenerateTask = async (taskId: string): Promise<GenerateStatus> => {
  for (;;) {
    const status = await getGenerateStatus(taskId);
    if (status.status === 'SUCCESS' || status.status === 'FAILURE') {
      return status;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
};

/** Poll multiple tasks until all reach a terminal state. */
export const waitForGenerateTasks = async (taskIds: string[]): Promise<GenerateStatus[]> => {
  for (;;) {
    const statuses = await Promise.all(taskIds.map(getGenerateStatus));
    if (statuses.every((item) => item.status === 'SUCCESS' || item.status === 'FAILURE')) {
      return statuses;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
};