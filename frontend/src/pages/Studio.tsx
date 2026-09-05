import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Play, RefreshCw, FileText, Image, Send, CheckCircle, X, BookmarkPlus, Download } from 'lucide-react';
import type { BrandSummary } from '@/api/brands';
import type { Product } from '@/api/products';
import { getProducts } from '@/api/products';
import {
  generateContent,
  generateCopywriting,
  generateImage,
  persistCompareSelection,
  aggregateGenerateProgress,
  buildGenerateProgressLayout,
  fetchGenerateStatuses,
  POLL_INTERVAL_DEGRADED_MS,
  POLL_INTERVAL_MS,
  POLL_STALL_CONSECUTIVE_FAILURES,
  POLL_WARN_CONSECUTIVE_FAILURES,
  POLL_INTERVAL_STALLED_MS,
  resolveReferenceSelection,
  type GenerateRequest,
  type GenerateStatus,
  type DimensionInfo,
  type ReferenceDiagnostics,
  type GenerationDiagnostics,
} from '@/api/generate';
import { publishContent } from '@/api/publish';
import { createDraft } from '@/api/tasks';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import ReferenceImagesDisplay from '@/components/ReferenceImagesDisplay';
import DimensionInfoDisplay, { CopyablePromptBlock } from '@/components/DimensionInfoDisplay';
import ImageModelPicker from '@/components/ImageModelPicker';
import ImageGenerationControls from '@/components/ImageGenerationControls';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import SocialFeedPreview from '@/components/SocialFeedPreview';
import GeneratedImagePanel from '@/components/GeneratedImagePanel';
import BrandAvatar from '@/components/BrandAvatar';
import PlatformIcon from '@/components/icons/PlatformIcon';
import type { PlatformId } from '@/components/icons/PlatformIcon';
import { getAuthUserId, studioStateStorageKey } from '@/api/auth';
import { useBrandContext } from '@/context/BrandContext';
import { toast } from '@/lib/feedback';
import PublishProgressOverlay, { usePublishPhaseRunner } from '@/components/PublishProgressOverlay';
import { useI18n } from '@/i18n/useI18n';
import { downloadImage } from '@/lib/download';
import { resolveEffectiveLogoMode } from '@/lib/logoPolicy';
import { areDimensionsAllNull } from '@/lib/dimensionDisplay';
import { STUDIO_REFERENCE_COUNT_MAX } from '@/lib/imageGenerationControls';

import { PLATFORMS, platformLabel } from '@/lib/platformLabels';
import {
  extractApiDetail,
  isConnectionError,
  sanitizeMessage,
  toUserFacingMessage,
} from '@/lib/apiErrors';

type ScenePipelineKey = 'legacy_scene' | 'vision_scene';

interface ScenePipelineSlot {
  image: string;
  image_prompt?: string;
  dimensions?: DimensionInfo;
  warning?: string;
  warning_code?: string;
  reference_diagnostics?: ReferenceDiagnostics;
  reference_product_images?: string[];
  reference_scene_images?: string[];
  generation_diagnostics?: GenerationDiagnostics;
  error?: string;
}

type CompareSceneResults = Record<ScenePipelineKey, ScenePipelineSlot | null>;

type GenerateType = 'all' | 'copywriting' | 'image';

type PollHealth = 'ok' | 'degraded' | 'stalled';

const OPTIMISTIC_GENERATE_STATUS: GenerateStatus = {
  task_id: '',
  status: 'PROGRESS',
  progress: 2,
  stage: 'starting',
};

function compactSelectorReason(
  reason: string | undefined,
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  if (!reason) return '';
  if (reason === 'limited_references') return t('preview.selectorReasonLimited');
  if (reason === 'stable_primary') return t('preview.selectorReasonStable');
  if (reason === 'safe_rotation') return t('preview.selectorReasonRotated');
  return reason;
}

function optimisticStatusForStage(
  stage: string,
  progress: number,
  prev?: GenerateStatus | null,
): GenerateStatus {
  return {
    task_id: prev?.task_id ?? '',
    status: 'PROGRESS',
    progress: Math.max(prev?.progress ?? 0, progress),
    stage,
  };
}

function resolvePendingTaskIds(saved: PreviewState): string[] {
  if (saved.taskIds?.length) return saved.taskIds;
  if (saved.taskId) return [saved.taskId];
  return [];
}

function slotFromStatus(status: GenerateStatus): ScenePipelineSlot | null {
  const result = status.result;
  if (status.status === 'PENDING' || status.status === 'PROGRESS') {
    return null;
  }
  if (status.status === 'FAILURE' || !result?.image) {
    return {
      image: '',
      error: result?.error || 'Generation failed',
    };
  }
  return {
    image: result.image || '',
    image_prompt: result.image_prompt,
    dimensions: result.dimensions,
    warning: result.warning,
    warning_code: result.warning_code,
    reference_diagnostics: result.reference_diagnostics,
    reference_product_images: result.reference_product_images,
    reference_scene_images: result.reference_scene_images,
    generation_diagnostics: result.generation_diagnostics,
  };
}

type PipelineDisplayState = {
  isGenerating: boolean;
  progress: number;
  stage: string | null;
};

function resolvePipelineDisplay(
  taskStatus: GenerateStatus | undefined,
  batchGenerating: boolean,
  copyStatus: GenerateStatus | undefined,
  generatingType: GenerateType | null,
): PipelineDisplayState {
  if (!batchGenerating) {
    return {
      isGenerating: false,
      progress: taskStatus?.status === 'SUCCESS' ? 100 : (taskStatus?.progress ?? 0),
      stage: taskStatus?.stage ?? null,
    };
  }

  if (!taskStatus) {
    if (generatingType === 'all' && copyStatus && isInFlightStatus(copyStatus.status)) {
      return {
        isGenerating: true,
        progress: copyStatus.progress ?? 0,
        stage: copyStatus.stage ?? 'copywriting',
      };
    }
    if (generatingType === 'all' && copyStatus?.status === 'SUCCESS') {
      return { isGenerating: true, progress: 0, stage: 'image_prompt' };
    }
    return { isGenerating: true, progress: 0, stage: 'queued' };
  }

  if (isInFlightStatus(taskStatus.status)) {
    return {
      isGenerating: true,
      progress: taskStatus.progress ?? 0,
      stage: taskStatus.stage ?? 'image_generation',
    };
  }

  return { isGenerating: false, progress: 100, stage: 'done' };
}

function statusMap(statuses: GenerateStatus[]): Map<string, GenerateStatus> {
  return new Map(statuses.map((s) => [s.task_id, s]));
}

function isInFlightStatus(status: string): boolean {
  return status === 'PENDING' || status === 'PROGRESS';
}

function isTerminalStatus(status: string): boolean {
  return status === 'SUCCESS' || status === 'FAILURE';
}

/** Compare-all: [copy, legacy, vision]; compare-image: [legacy, vision]. */
function inferCompareTaskLayout(
  taskIds: string[],
  generatingType: string | null,
  compareMode: boolean,
): { copyId?: string; legacyId: string; visionId: string } | null {
  if (!compareMode || taskIds.length < 2) return null;
  if (generatingType === 'all') {
    if (taskIds.length < 3) return null;
    return { copyId: taskIds[0], legacyId: taskIds[1], visionId: taskIds[2] };
  }
  if (generatingType === 'image') {
    return { legacyId: taskIds[0], visionId: taskIds[1] };
  }
  return null;
}

function isCompareAllBatchReady(
  taskIds: string[],
  generatingType: string | null,
  compareMode: boolean,
): boolean {
  return !compareMode || generatingType !== 'all' || taskIds.length >= 3;
}

interface PreviewState {
  selectedProduct: string;
  selectedPlatforms: string[];
  useSceneReference: boolean;
  useVisionImagePrompt: boolean;
  realisticPlacement: boolean;
  compareScenePipelines: boolean;
  referenceCount: number;
  imageProviderId?: string | null;
  imageModel?: string | null;
  imageSize?: string | null;
  generatedContent: {
    text: string;
    image: string;
    dimensions?: DimensionInfo;
    image_prompt?: string;
    reference_product_images?: string[];
    reference_scene_images?: string[];
    warning?: string;
    warning_code?: string;
    logo_mode?: string;
    reference_diagnostics?: ReferenceDiagnostics;
    generation_diagnostics?: GenerationDiagnostics;
  } | null;
  taskId: string | null;
  taskIds?: string[];
  isGenerating: boolean;
  generatingType: string | null;
}

const emptyPreviewState = (): PreviewState => ({
  selectedProduct: '',
  selectedPlatforms: ['instagram'],
  useSceneReference: false,
  useVisionImagePrompt: false,
  realisticPlacement: true,
  compareScenePipelines: true,
  referenceCount: 2,
  imageProviderId: null,
  imageModel: null,
  imageSize: '2048x2048',
  generatedContent: null,
  taskId: null,
  taskIds: [],
  isGenerating: false,
  generatingType: null,
});

const loadStateFromStorage = (userId: string | null): PreviewState => {
  if (!userId) return emptyPreviewState();
  try {
    const saved = localStorage.getItem(studioStateStorageKey(userId));
    if (saved) {
      return JSON.parse(saved) as PreviewState;
    }
  } catch (e) {
    console.error('Failed to load state from localStorage:', e);
  }
  return emptyPreviewState();
};

const saveStateToStorage = (userId: string | null, state: PreviewState) => {
  if (!userId) return;
  try {
    localStorage.setItem(studioStateStorageKey(userId), JSON.stringify(state));
  } catch (e) {
    console.error('Failed to save state to localStorage:', e);
  }
};

interface StudioProps {
  /** False when another sidebar tab is active (Studio stays mounted but hidden). */
  isPageActive?: boolean;
}

export default function Studio({ isPageActive = true }: StudioProps) {
  const { t, locale } = useI18n();
  const { activeBrandId, activeBrand, brands, setBrandFilterLoading } = useBrandContext();
  const userId = getAuthUserId();
  const savedState = loadStateFromStorage(userId);
  
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<string>(savedState.selectedProduct);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(savedState.selectedPlatforms);
  const [useSceneReference, setUseSceneReference] = useState(savedState.useSceneReference);
  const [useVisionImagePrompt, setUseVisionImagePrompt] = useState(
    savedState.useVisionImagePrompt ?? false
  );
  const [realisticPlacement, setRealisticPlacement] = useState(
    savedState.realisticPlacement ?? true
  );
  const [compareScenePipelines, setCompareScenePipelines] = useState(
    savedState.compareScenePipelines ?? true
  );
  const [referenceCount, setReferenceCount] = useState(
    Math.min(savedState.referenceCount ?? 2, STUDIO_REFERENCE_COUNT_MAX),
  );
  // Provider starts as platform default (empty); ImageModelPicker may switch to BYOK.
  // Do not restore last session override from localStorage.
  const [imageProviderId, setImageProviderId] = useState<string | null>(null);
  const [imageModel, setImageModel] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState<string | null>(savedState.imageSize ?? '2048x2048');
  const [imageProviderMode, setImageProviderMode] = useState<'platform' | 'byok' | null>('platform');
  const pendingOnMount =
    !!savedState.generatingType && resolvePendingTaskIds(savedState).length > 0;
  const [isGenerating, setIsGenerating] = useState(pendingOnMount);
  const [generatingType, setGeneratingType] = useState<string | null>(
    pendingOnMount ? savedState.generatingType : null,
  );
  const [activeTaskIds, setActiveTaskIds] = useState<string[]>(() =>
    pendingOnMount ? resolvePendingTaskIds(savedState) : [],
  );
  const [generateStatus, setGenerateStatus] = useState<GenerateStatus | null>(null);
  const [generatedContent, setGeneratedContent] = useState<{
    text: string;
    image: string;
    dimensions?: DimensionInfo;
    image_prompt?: string;
    reference_product_images?: string[];
    reference_scene_images?: string[];
    warning?: string;
    warning_code?: string;
    logo_mode?: string;
    reference_diagnostics?: ReferenceDiagnostics;
    generation_diagnostics?: GenerationDiagnostics;
  } | null>(savedState.generatedContent);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishStatus, setPublishStatus] = useState<string | null>(null);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [saveDraftStatus, setSaveDraftStatus] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [productsLoading, setProductsLoading] = useState(true);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [compareResults, setCompareResults] = useState<CompareSceneResults | null>(null);
  const [taskStatuses, setTaskStatuses] = useState<GenerateStatus[]>([]);
  const [activePipeline, setActivePipeline] = useState<ScenePipelineKey>('vision_scene');
  const { publishOverlay, runPublishWithProgress } = usePublishPhaseRunner();
  const monotonicProgressRef = useRef(0);
  const compareGroupIdRef = useRef<string | null>(null);
  const taskStatusesRef = useRef<GenerateStatus[]>([]);
  const consecutivePollFailuresRef = useRef(0);
  const pollInFlightRef = useRef(false);
  const [pollHealth, setPollHealth] = useState<PollHealth>('ok');
  const [isRefreshingStatus, setIsRefreshingStatus] = useState(false);

  const progressLayout = useMemo(
    () =>
      buildGenerateProgressLayout(activeTaskIds, {
        generatingType: generatingType as GenerateType | null,
        compareMode:
          (generatingType === 'image' || generatingType === 'all') &&
          useSceneReference &&
          compareScenePipelines,
      }),
    [activeTaskIds, generatingType, useSceneReference, compareScenePipelines],
  );

  const applyAggregateStatus = useCallback(
    (
      statuses: GenerateStatus[],
      taskId: string,
      layoutOverride?: ReturnType<typeof buildGenerateProgressLayout>,
    ) => {
      const layout = layoutOverride ?? progressLayout;
      const aggregate = aggregateGenerateProgress(statuses, layout);
      const nextProgress = Math.max(monotonicProgressRef.current, aggregate.progress ?? 0);
      monotonicProgressRef.current = nextProgress;
      setGenerateStatus({
        task_id: taskId,
        status: aggregate.status ?? 'PROGRESS',
        progress: nextProgress,
        stage: aggregate.stage,
      });
    },
    [progressLayout],
  );

  const finishGeneration = useCallback(
    (outcome: 'SUCCESS' | 'FAILURE', opts?: { error?: string; taskId?: string }) => {
      monotonicProgressRef.current = 0;
      consecutivePollFailuresRef.current = 0;
      setPollHealth('ok');
      setIsRefreshingStatus(false);
      setIsGenerating(false);
      setGeneratingType(null);
      setActiveTaskIds([]);
      setTaskStatuses([]);
      taskStatusesRef.current = [];
      if (outcome === 'SUCCESS') {
        setGenerateStatus({
          task_id: opts?.taskId ?? '',
          status: 'SUCCESS',
          progress: 100,
          stage: 'done',
        });
      } else {
        setGenerateStatus({
          task_id: opts?.taskId ?? '',
          status: 'FAILURE',
          result: { error: opts?.error ?? 'Generation failed' },
        });
      }
    },
    [],
  );

  const applyPartialResults = useCallback(
    (
      statuses: GenerateStatus[],
      genType: GenerateType | null,
      compareMode: boolean,
      taskIds: string[],
    ) => {
      const layout = inferCompareTaskLayout(taskIds, genType, compareMode);
      if (layout?.copyId) {
        const copyStatus = statusMap(statuses).get(layout.copyId);
        if (copyStatus?.status === 'SUCCESS' && copyStatus.result?.text) {
          setGeneratedContent((prev) => ({
            ...(prev || { text: '', image: '' }),
            text: copyStatus.result!.text!,
            image: prev?.image || '',
            dimensions: prev?.dimensions,
            image_prompt: prev?.image_prompt,
            reference_product_images: prev?.reference_product_images,
            reference_scene_images: prev?.reference_scene_images,
            warning: prev?.warning,
            logo_mode: prev?.logo_mode,
          }));
        }
      }

      if (layout?.legacyId && layout?.visionId) {
        const byId = statusMap(statuses);
        const legacyStatus = byId.get(layout.legacyId);
        const visionStatus = byId.get(layout.visionId);
        setCompareResults({
          legacy_scene: legacyStatus ? slotFromStatus(legacyStatus) : null,
          vision_scene: visionStatus ? slotFromStatus(visionStatus) : null,
        });
      }

      if (!layout && statuses.length === 1 && statuses[0].status === 'SUCCESS' && statuses[0].result) {
        const s = statuses[0];
        setGeneratedContent((prev) => ({
          text: s.result?.text || prev?.text || '',
          image: s.result?.image || prev?.image || '',
          dimensions: s.result?.dimensions ?? prev?.dimensions,
          image_prompt: s.result?.image_prompt ?? prev?.image_prompt,
          reference_product_images:
            s.result?.reference_product_images ?? prev?.reference_product_images,
          reference_scene_images:
            s.result?.reference_scene_images ?? prev?.reference_scene_images,
          warning: s.result?.warning ?? prev?.warning,
          warning_code: s.result?.warning_code ?? prev?.warning_code,
          logo_mode: s.result?.logo_mode ?? prev?.logo_mode,
          reference_diagnostics: s.result?.reference_diagnostics ?? prev?.reference_diagnostics,
          generation_diagnostics: s.result?.generation_diagnostics ?? prev?.generation_diagnostics,
        }));
      }
    },
    [],
  );

  const applyRecoveredResults = useCallback(
    (
      statuses: GenerateStatus[],
      genType: GenerateType | null,
      compareMode: boolean,
      taskIds: string[],
    ) => {
      const layout = inferCompareTaskLayout(taskIds, genType, compareMode);
      if (layout?.legacyId && layout.visionId) {
        const byId = statusMap(statuses);
        const legacyStatus = byId.get(layout.legacyId);
        const visionStatus = byId.get(layout.visionId);
        const copyStatus = layout.copyId ? byId.get(layout.copyId) : undefined;
        const results: CompareSceneResults = {
          legacy_scene: legacyStatus ? slotFromStatus(legacyStatus) : null,
          vision_scene: visionStatus ? slotFromStatus(visionStatus) : null,
        };
        setCompareResults(results);

        const copyText = copyStatus?.result?.text || '';
        const visionSlot = results.vision_scene;
        const legacySlot = results.legacy_scene;
        const primary =
          visionSlot?.image && !visionSlot.error ? visionSlot : legacySlot;
        const primaryKey: ScenePipelineKey =
          visionSlot?.image && !visionSlot.error ? 'vision_scene' : 'legacy_scene';

        if (primary?.image) {
          setGeneratedContent((prev) => ({
            text: copyText || prev?.text || '',
            image: primary.image,
            dimensions: primary.dimensions,
            image_prompt: primary.image_prompt,
            reference_product_images: primary.reference_product_images,
            reference_scene_images: primary.reference_scene_images,
            warning: primary.warning,
            logo_mode: undefined,
            generation_diagnostics: primary.generation_diagnostics,
          }));
          setActivePipeline(primaryKey);
        } else if (copyText) {
          setGeneratedContent((prev) => ({
            ...(prev || { text: '', image: '' }),
            text: copyText,
          }));
        }

        const anyImage = !!(legacySlot?.image || visionSlot?.image);
        if (anyImage) {
          finishGeneration('SUCCESS', { taskId: taskIds[0] });
          window.dispatchEvent(new Event('pulseforge:refresh-user'));
        } else {
          const errors = statuses
            .filter((s) => s.status === 'FAILURE')
            .map((s) => s.result?.error)
            .filter(Boolean);
          finishGeneration('FAILURE', {
            taskId: taskIds[0],
            error: errors.join(' · ') || undefined,
          });
        }
        return;
      }

      const status = statuses[0];
      if (compareMode && genType === 'all') {
        return;
      }
      if (status?.status === 'SUCCESS' && status.result) {
        setGeneratedContent((prev) => ({
          text: status.result?.text || prev?.text || '',
          image: status.result?.image || prev?.image || '',
          dimensions: status.result?.dimensions ?? prev?.dimensions,
          image_prompt: status.result?.image_prompt ?? prev?.image_prompt,
          reference_product_images:
            status.result?.reference_product_images ?? prev?.reference_product_images,
          reference_scene_images:
            status.result?.reference_scene_images ?? prev?.reference_scene_images,
          warning: status.result?.warning ?? prev?.warning,
          warning_code: status.result?.warning_code ?? prev?.warning_code,
          logo_mode: status.result?.logo_mode ?? prev?.logo_mode,
          reference_diagnostics:
            status.result?.reference_diagnostics ?? prev?.reference_diagnostics,
          generation_diagnostics:
            status.result?.generation_diagnostics ?? prev?.generation_diagnostics,
        }));
        finishGeneration('SUCCESS', { taskId: status.task_id });
        window.dispatchEvent(new Event('pulseforge:refresh-user'));
      } else if (status?.status === 'FAILURE') {
        finishGeneration('FAILURE', {
          taskId: status.task_id,
          error: status.result?.error,
        });
      }
    },
    [finishGeneration],
  );

  const recordPollOutcome = useCallback((allSucceeded: boolean) => {
    if (allSucceeded) {
      consecutivePollFailuresRef.current = 0;
      setPollHealth('ok');
      return;
    }
    consecutivePollFailuresRef.current += 1;
    const failures = consecutivePollFailuresRef.current;
    if (failures >= POLL_STALL_CONSECUTIVE_FAILURES) {
      setPollHealth('stalled');
    } else if (failures >= POLL_WARN_CONSECUTIVE_FAILURES) {
      setPollHealth('degraded');
    }
  }, []);

  const processPollRound = useCallback(
    (
      statuses: GenerateStatus[],
      pollSucceeded: boolean,
    ): boolean => {
      recordPollOutcome(pollSucceeded);
      taskStatusesRef.current = statuses;
      setTaskStatuses(statuses);
      applyAggregateStatus(statuses, activeTaskIds[0]);

      const compareMode =
        (generatingType === 'image' || generatingType === 'all') &&
        useSceneReference &&
        compareScenePipelines;

      applyPartialResults(
        statuses,
        generatingType as GenerateType | null,
        compareMode,
        activeTaskIds,
      );

      const allTerminal = statuses.every((s) => isTerminalStatus(s.status));
      const compareAllReady = isCompareAllBatchReady(
        activeTaskIds,
        generatingType,
        compareMode,
      );

      if (allTerminal && compareAllReady) {
        applyRecoveredResults(
          statuses,
          generatingType as GenerateType | null,
          compareMode,
          activeTaskIds,
        );
        return true;
      }
      return false;
    },
    [
      activeTaskIds,
      generatingType,
      useSceneReference,
      compareScenePipelines,
      applyAggregateStatus,
      applyPartialResults,
      applyRecoveredResults,
      recordPollOutcome,
    ],
  );

  const runStatusPoll = useCallback(async (): Promise<boolean> => {
    if (activeTaskIds.length === 0) return false;
    const previousById = statusMap(taskStatusesRef.current);
    const { statuses, allSucceeded } = await fetchGenerateStatuses(
      activeTaskIds,
      previousById,
    );
    return processPollRound(statuses, allSucceeded);
  }, [activeTaskIds, processPollRound]);

  const handleManualRefreshStatus = async () => {
    if (activeTaskIds.length === 0 || isRefreshingStatus) return;
    setIsRefreshingStatus(true);
    try {
      await runStatusPoll();
    } catch (error) {
      console.error('Failed to refresh generate status:', error);
      toast.error(t('preview.pollRefreshFailed'));
    } finally {
      setIsRefreshingStatus(false);
    }
  };

  const previewBrand = useMemo((): BrandSummary | null => {
    const product = products.find((p) => p.product_id === selectedProduct);
    if (!product) return activeBrand;

    const brandId = product.brand_id ?? product.brand?.brand_id;
    if (brandId) {
      const brand = brands.find((b) => b.brand_id === brandId);
      if (brand) return brand;
      // 产品上嵌套了他人品牌摘要时只用于展示，不另发 getBrand
      if (product.brand) {
        return {
          brand_id: product.brand.brand_id,
          slug: product.brand.slug,
          name: product.brand.name,
          is_generic: false,
          is_system: false,
          product_count: 0,
        };
      }
    }
    return activeBrand;
  }, [selectedProduct, products, brands, activeBrand]);

  const previewBrandName = previewBrand
    ? previewBrand.is_generic
      ? t('brands.generic')
      : previewBrand.name
    : t('brand.name');

  const previewBrandLogo = previewBrand?.logo_url ?? null;

  const selectedProductRecord = useMemo(
    () => products.find((p) => p.product_id === selectedProduct) ?? null,
    [products, selectedProduct],
  );

  const effectiveLogoMode = useMemo(
    () => resolveEffectiveLogoMode(previewBrand, selectedProductRecord),
    [previewBrand, selectedProductRecord],
  );

  const brandingModeLabel = useMemo(() => {
    const mode = effectiveLogoMode;
    if (mode === 'omit') return t('studio.brandingOmit');
    if (mode === 'composite') return t('studio.brandingComposite');
    return t('studio.brandingPreserve');
  }, [effectiveLogoMode, t]);

  const generateActionsDisabled =
    isGenerating || !selectedProduct || selectedPlatforms.length === 0;

  const generationProgress = generateStatus?.progress ?? (isGenerating ? 2 : 0);
  const generationStage = generateStatus?.stage ?? (isGenerating ? 'starting' : null);

  const comparePreviewActive = useMemo(() => {
    if (!useSceneReference || !compareScenePipelines) return false;
    if (compareResults !== null) return true;
    return isGenerating && (generatingType === 'all' || generatingType === 'image');
  }, [
    useSceneReference,
    compareScenePipelines,
    compareResults,
    isGenerating,
    generatingType,
  ]);

  const comparePipelineDisplay = useMemo((): Record<
    ScenePipelineKey,
    PipelineDisplayState
  > | null => {
    if (!comparePreviewActive) return null;

    const compareMode =
      generatingType === 'image' || generatingType === 'all';
    const layout = inferCompareTaskLayout(activeTaskIds, generatingType, compareMode);
    const byId = statusMap(taskStatuses);
    const copyStatus = layout?.copyId ? byId.get(layout.copyId) : undefined;
    const legacyStatus = layout?.legacyId ? byId.get(layout.legacyId) : undefined;
    const visionStatus = layout?.visionId ? byId.get(layout.visionId) : undefined;

    return {
      legacy_scene: resolvePipelineDisplay(
        legacyStatus,
        isGenerating,
        copyStatus,
        generatingType as GenerateType | null,
      ),
      vision_scene: resolvePipelineDisplay(
        visionStatus,
        isGenerating,
        copyStatus,
        generatingType as GenerateType | null,
      ),
    };
  }, [
    comparePreviewActive,
    activeTaskIds,
    generatingType,
    taskStatuses,
    isGenerating,
  ]);

  useEffect(() => {
    if (!savedState.generatingType) return;

    const pendingTaskIds = resolvePendingTaskIds(savedState);
    if (!pendingTaskIds.length) return;

    let cancelled = false;
    const compareMode =
      (savedState.generatingType === 'image' || savedState.generatingType === 'all') &&
      savedState.useSceneReference &&
      savedState.compareScenePipelines;

    const recoverTasks = async () => {
      try {
        const { statuses } = await fetchGenerateStatuses(pendingTaskIds);
        if (cancelled) return;
        taskStatusesRef.current = statuses;
        setTaskStatuses(statuses);

        const recoverLayout = buildGenerateProgressLayout(pendingTaskIds, {
          generatingType: savedState.generatingType as GenerateType,
          compareMode,
        });
        applyAggregateStatus(statuses, pendingTaskIds[0], recoverLayout);

        const anyInFlight = statuses.some((s) => isInFlightStatus(s.status));
        if (anyInFlight) {
          setIsGenerating(true);
          setActiveTaskIds(pendingTaskIds);
          setGeneratingType(savedState.generatingType);
          applyPartialResults(
            statuses,
            savedState.generatingType as GenerateType,
            compareMode,
            pendingTaskIds,
          );
          return;
        }

        applyRecoveredResults(
          statuses,
          savedState.generatingType as GenerateType,
          compareMode,
          pendingTaskIds,
        );
      } catch (error) {
        if (cancelled) return;
        console.error('Failed to recover generate tasks:', error);
        setIsGenerating(true);
        setActiveTaskIds(pendingTaskIds);
        setGeneratingType(savedState.generatingType);
      }
    };

    void recoverTasks();
    return () => {
      cancelled = true;
    };
    // Only reconcile persisted tasks once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setSelectedProduct('');
    setProducts([]);
    void loadProducts();
  }, [activeBrandId]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadProducts(true);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    saveStateToStorage(userId, {
      selectedProduct,
      selectedPlatforms,
      useSceneReference,
      useVisionImagePrompt,
      realisticPlacement,
      compareScenePipelines,
      referenceCount,
      imageProviderId,
      imageModel,
      imageSize,
      generatedContent,
      taskId: isGenerating ? (activeTaskIds[0] ?? null) : null,
      taskIds: isGenerating ? activeTaskIds : [],
      isGenerating: false,
      generatingType: isGenerating ? generatingType : null,
    });
  }, [userId, selectedProduct, selectedPlatforms, useSceneReference, useVisionImagePrompt, realisticPlacement, compareScenePipelines, referenceCount, imageProviderId, imageModel, imageSize, generatedContent, activeTaskIds, isGenerating, generatingType]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    if (!isGenerating || activeTaskIds.length === 0 || !isPageActive) {
      return () => {
        if (interval) clearInterval(interval);
      };
    }

    const pollIntervalMs =
      pollHealth === 'stalled'
        ? POLL_INTERVAL_STALLED_MS
        : pollHealth === 'degraded'
          ? POLL_INTERVAL_DEGRADED_MS
          : POLL_INTERVAL_MS;

    const checkStatus = async () => {
      if (!isPageActive || pollInFlightRef.current) return;
      pollInFlightRef.current = true;
      try {
        const done = await runStatusPoll();
        if (done && interval) clearInterval(interval);
      } catch (error) {
        recordPollOutcome(false);
        console.error('Failed to check status:', error);
      } finally {
        pollInFlightRef.current = false;
      }
    };

    void checkStatus();
    interval = setInterval(checkStatus, pollIntervalMs);
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [
    activeTaskIds,
    isGenerating,
    isPageActive,
    pollHealth,
    runStatusPoll,
    recordPollOutcome,
  ]);

  // One immediate poll when returning to Studio while a task is still in flight.
  useEffect(() => {
    if (!isPageActive || !isGenerating || activeTaskIds.length === 0) return;
    if (pollInFlightRef.current) return;
    pollInFlightRef.current = true;
    void runStatusPoll()
      .catch((error) => {
        recordPollOutcome(false);
        console.error('Failed to refresh status on tab focus:', error);
      })
      .finally(() => {
        pollInFlightRef.current = false;
      });
  }, [isPageActive]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadProducts = async (force = false) => {
    if (!force) setProductsLoading(true);
    const cacheKey = `products:list:100:${activeBrandId || 'all'}`;
    try {
      if (force) invalidateCache(cacheKey);
      const data = force
        ? (await getProducts(1, 100, activeBrandId || undefined)).data
        : await cachedFetch(cacheKey, async () => {
            const response = await getProducts(1, 100, activeBrandId || undefined);
            return response.data;
          });
      setProducts(data);
      // 仅在没有已选产品时设默认，避免覆盖 localStorage
      setSelectedProduct((prev) => {
        if (prev && data.some((p) => p.product_id === prev)) return prev;
        return data[0]?.product_id ?? '';
      });
    } catch (error) {
      console.error('Failed to load products:', error);
    } finally {
      setProductsLoading(false);
      setBrandFilterLoading(false);
    }
  };

  const buildGenerateRequest = (type: 'all' | 'copywriting' | 'image'): GenerateRequest => ({
    product_id: selectedProduct,
    platform: selectedPlatforms[0],
    style_hint: 'storytelling',
    use_scene_reference: useSceneReference,
    use_vision_image_prompt: useVisionImagePrompt,
    realistic_placement: realisticPlacement,
    reference_count: referenceCount,
    image_provider_id: imageProviderId || undefined,
    image_model: imageModel || undefined,
    image_size: imageSize || undefined,
    image_provider_mode: type === 'copywriting' ? undefined : imageProviderMode || undefined,
    locale,
  });

  const applyPipelineSlotToContent = (
    slot: ScenePipelineSlot,
    pipeline: ScenePipelineKey,
    prevText: string
  ) => {
    setGeneratedContent((prev) => ({
      text: prevText || prev?.text || '',
      image: slot.image,
      dimensions: slot.dimensions,
      image_prompt: slot.image_prompt,
      reference_product_images: slot.reference_product_images,
      reference_scene_images: slot.reference_scene_images,
      warning: slot.warning,
      logo_mode: undefined,
      generation_diagnostics: slot.generation_diagnostics,
    }));
    setActivePipeline(pipeline);
  };

  const startCompareImageGeneration = async (
    baseRequest: GenerateRequest,
    prevText: string,
    onImageTasksStarted?: (taskIds: [string, string]) => void,
  ): Promise<[string, string]> => {
    setGenerateStatus((prev) =>
      optimisticStatusForStage('resolving_references', 3, prev),
    );

    const refs = await resolveReferenceSelection({
      product_id: baseRequest.product_id,
      reference_count: baseRequest.reference_count,
      use_scene_reference: true,
      image_size: baseRequest.image_size || undefined,
    });

    setGeneratedContent((prev) => ({
      text: prev?.text || prevText,
      image: prev?.image || '',
      reference_product_images: refs.reference_product_images,
      reference_scene_images: refs.reference_scene_images,
      generation_diagnostics: refs.generation_diagnostics,
    }));

    setGenerateStatus((prev) => optimisticStatusForStage('starting', 5, prev));

    const compareGroupId =
      typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `cmp-${Date.now()}`;
    compareGroupIdRef.current = compareGroupId;
    const pinned = {
      reference_product_images: refs.reference_product_images,
      reference_scene_images: refs.reference_scene_images,
      reference_product_image_ids: refs.reference_product_image_ids,
      reference_scene_image_ids: refs.reference_scene_image_ids,
      compare_group_id: compareGroupId,
    };

    const legacyReq: GenerateRequest = {
      ...baseRequest,
      ...pinned,
      use_scene_reference: true,
      use_vision_image_prompt: false,
      image_prompt_pipeline: 'legacy_scene',
    };
    const visionReq: GenerateRequest = {
      ...baseRequest,
      ...pinned,
      use_scene_reference: true,
      use_vision_image_prompt: true,
      image_prompt_pipeline: 'vision_scene',
    };

    const [legacyStart, visionStart] = await Promise.all([
      generateImage(legacyReq),
      generateImage(visionReq),
    ]);
    const taskIds: [string, string] = [legacyStart.task_id, visionStart.task_id];
    onImageTasksStarted?.(taskIds);
    return taskIds;
  };

  const shouldCompareScenePipelines = (type: 'all' | 'copywriting' | 'image') =>
    (type === 'image' || type === 'all') &&
    useSceneReference &&
    compareScenePipelines;

  const handleGenerate = async (type: 'all' | 'copywriting' | 'image') => {
    if (!selectedProduct) {
      toast.info(t('preview.selectProductFirst'));
      return;
    }
    if (selectedPlatforms.length === 0) {
      toast.info(t('preview.selectPlatform'));
      return;
    }
    if (isGenerating) return;

    monotonicProgressRef.current = OPTIMISTIC_GENERATE_STATUS.progress ?? 2;
    consecutivePollFailuresRef.current = 0;
    setPollHealth('ok');
    setIsRefreshingStatus(false);
    setIsGenerating(true);
    setGeneratingType(type);
    setPublishStatus(null);
    setSaveDraftStatus(null);
    setActiveTaskIds([]);
    setGenerateStatus(OPTIMISTIC_GENERATE_STATUS);
    
    if (type === 'copywriting') {
      setGeneratedContent(prev => ({
        text: '',
        image: prev?.image || '',
        dimensions: prev?.dimensions,
        image_prompt: prev?.image_prompt,
        reference_product_images: prev?.reference_product_images,
        reference_scene_images: prev?.reference_scene_images,
        warning: prev?.warning,
      }));
    } else if (type === 'image') {
      setGeneratedContent(prev => ({
        text: prev?.text || '',
        image: '',
        dimensions: undefined,
        image_prompt: undefined,
        reference_product_images: undefined,
        reference_scene_images: undefined,
        warning: undefined,
      }));
    } else if (shouldCompareScenePipelines(type)) {
      setGeneratedContent(() => ({
        text: '',
        image: '',
        dimensions: undefined,
        image_prompt: undefined,
        reference_product_images: undefined,
        reference_scene_images: undefined,
        warning: undefined,
      }));
    } else {
      setGeneratedContent(null);
    }
    setTaskStatuses([]);
    taskStatusesRef.current = [];
    if (shouldCompareScenePipelines(type)) {
      setCompareResults({ legacy_scene: null, vision_scene: null });
    } else {
      setCompareResults(null);
    }

    let startedTaskIds: string[] = [];

    try {
      const request = buildGenerateRequest(type);

      const useCompare = shouldCompareScenePipelines(type);

      if (useCompare) {
        const prevText =
          type === 'image' ? generatedContent?.text || '' : '';

        if (type === 'all') {
          const copyStart = await generateCopywriting(request);
          const imageTaskIds = await startCompareImageGeneration(request, '');
          startedTaskIds = [copyStart.task_id, ...imageTaskIds];
          setActiveTaskIds(startedTaskIds);
        } else {
          const imageTaskIds = await startCompareImageGeneration(request, prevText, (ids) => {
            startedTaskIds = ids;
            setActiveTaskIds(ids);
          });
          startedTaskIds = imageTaskIds;
          setActiveTaskIds(startedTaskIds);
        }

        return;
      }

      let response;
      if (type === 'copywriting') {
        response = await generateCopywriting(request);
      } else if (type === 'image') {
        response = await generateImage(request);
      } else {
        response = await generateContent(request);
      }
      startedTaskIds = [response.task_id];
      setActiveTaskIds(startedTaskIds);
    } catch (error: unknown) {
      console.error('Failed to generate content:', error);
      const detail = extractApiDetail(error);
      const statusCode =
        error && typeof error === 'object' && 'response' in error
          ? (error as { response?: { status?: number } }).response?.status
          : undefined;

      if (startedTaskIds.length > 0) {
        setIsGenerating(true);
        setActiveTaskIds(startedTaskIds);
        toast.info(t('preview.connectionRetry'));
        return;
      }

      const message = toUserFacingMessage(error, t('preview.generateFailed'));
      finishGeneration('FAILURE', { error: message });
      if (statusCode === 402) {
        toast.error(sanitizeMessage(detail, t('imageModelPicker.creditsExhausted')));
      } else if (statusCode === 503) {
        toast.error(sanitizeMessage(detail, t('imageModelPicker.systemUnavailable')));
      } else if (isConnectionError(error)) {
        toast.error(t('preview.connectionRetry'));
      } else {
        toast.error(message);
      }
    }
  };

  const handlePublish = async () => {
    if (!generatedContent || !generatedContent.text) {
      toast.info(t('preview.generateCopyFirst'));
      return;
    }
    if (selectedPlatforms.length === 0) {
      toast.info(t('preview.selectPlatform'));
      return;
    }
    const boundBrand =
      brands.find((b) => b.brand_id === previewBrand?.brand_id) || previewBrand;
    if (boundBrand && 'buffer_account_id' in boundBrand && !boundBrand.buffer_account_id) {
      toast.error(
        t('preview.bindBufferAccount', {
          name: boundBrand.is_generic ? t('brands.generic') : boundBrand.name,
        })
      );
      return;
    }
    
    setIsPublishing(true);
    setPublishStatus(null);
    
    try {
      await runPublishWithProgress(
        () =>
          publishContent(
            generatedContent.text,
            generatedContent.image,
            selectedPlatforms,
            { product_id: selectedProduct || undefined, brand_id: boundBrand?.brand_id }
          ),
        selectedPlatforms
      );
      setPublishStatus('success');
      toast.success(t('preview.publishSuccess'));
    } catch (error: any) {
      console.error('Failed to publish content:', error);
      setPublishStatus('failed');
      toast.error(toUserFacingMessage(error, t('preview.publishFailed')));
    } finally {
      setIsPublishing(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!generatedContent?.text && !generatedContent?.image) {
      toast.info(t('preview.generateBeforeSave'));
      return;
    }

    setIsSavingDraft(true);
    setSaveDraftStatus(null);
    try {
      const images = generatedContent.image ? [generatedContent.image] : [];
      const copywritings = generatedContent.text ? [generatedContent.text] : [];
      await createDraft({
        product_id: selectedProduct || undefined,
        images,
        copywritings,
        dimensions: generatedContent.dimensions ? [generatedContent.dimensions] : [],
        image_prompts: generatedContent.image_prompt ? [generatedContent.image_prompt] : [],
        reference_product_images: generatedContent.reference_product_images || [],
        reference_scene_images: generatedContent.reference_scene_images || [],
      });
      invalidateCache('drafts');
      setSaveDraftStatus('success');
      window.dispatchEvent(new Event('pulseforge:refresh-user'));
    } catch (error) {
      console.error('Failed to save draft:', error);
      setSaveDraftStatus('failed');
      toast.error(t('preview.saveFailed'));
    } finally {
      setIsSavingDraft(false);
    }
  };

  const togglePlatform = (platform: string) => {
    setSelectedPlatforms(prev => {
      if (prev.includes(platform)) {
        if (prev.length === 1) return prev;
        return prev.filter(p => p !== platform);
      }
      return [...prev, platform];
    });
  };

  const pipelineLabel = (key: ScenePipelineKey) =>
    key === 'legacy_scene' ? t('studio.pipelineLegacy') : t('studio.pipelineVision');

  const selectPipelineForPublish = (key: ScenePipelineKey, slot: ScenePipelineSlot) => {
    applyPipelineSlotToContent(slot, key, generatedContent?.text || '');
    const groupId = compareGroupIdRef.current;
    if (!groupId) return;
    void persistCompareSelection({
      compare_group_id: groupId,
      image_prompt_pipeline: key,
    }).catch((error) => {
      console.error('Failed to persist compare selection', error);
    });
  };

  const renderComparePipelineCard = (key: ScenePipelineKey, slot: ScenePipelineSlot | null) => {
    const selected = activePipeline === key;
    const caption = generatedContent?.text || undefined;
    const pipelineDisplay = comparePipelineDisplay?.[key];
    const showGenerating = pipelineDisplay?.isGenerating ?? isGenerating;

    return (
      <div
        key={key}
        className={`rounded-xl border p-4 flex flex-col gap-3 ${
          selected ? 'border-forge-500 ring-2 ring-forge-100 bg-forge-50/30' : 'border-gray-200 bg-white'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-gray-900">{pipelineLabel(key)}</h3>
          {slot?.image && (
            <button
              type="button"
              onClick={() => selectPipelineForPublish(key, slot)}
              className={`text-xs px-2 py-1 rounded-md shrink-0 ${
                selected
                  ? 'bg-forge-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {selected ? t('studio.pipelineActive') : t('studio.pipelineUseForPublish')}
            </button>
          )}
        </div>
        {slot?.error && !slot.image && (
          <p className="text-sm text-red-600">{slot.error}</p>
        )}
        <div className="w-full max-w-[220px] mx-auto">
          <SocialFeedPreview
            platforms={selectedPlatforms}
            image={slot?.image || undefined}
            caption={caption}
            brandName={previewBrandName}
            brandLogo={previewBrandLogo}
            imageAlt={pipelineLabel(key)}
            onImageClick={slot?.image ? setPreviewImage : undefined}
            isGenerating={showGenerating}
            generatingType={generatingType}
            generationProgress={pipelineDisplay?.progress ?? generationProgress}
            generationStage={pipelineDisplay?.stage ?? generationStage}
          />
        </div>
        {slot?.image && (
          <GeneratedImagePanel
            imageUrl={slot.image}
            imageAlt={pipelineLabel(key)}
            onViewFullSize={setPreviewImage}
            filename={`${key}-${previewBrandName.toLowerCase().replace(/[^a-z0-9]/g, '') || 'brand'}.jpg`}
          />
        )}
        {slot?.warning && (
          <p className="text-xs text-amber-700">{slot.warning}</p>
        )}
      </div>
    );
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t('studio.title')}</h2>
          <p className="text-gray-500 mt-1">{t('studio.subtitle')}</p>
          {activeBrand && (
            <p className="text-xs text-forge-600 mt-1">
              {t('studio.inheritedFrom', { brand: activeBrand.is_generic ? t('brands.generic') : activeBrand.name })}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => void handleRefresh()}
          disabled={refreshing || isGenerating}
          className="flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {t('common.refresh')}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1 space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <LabelWithTooltip
              htmlFor="studio-product"
              label={t('fields.selectProduct')}
              tooltip={t('studio.tooltips.product')}
              required
            />
            {productsLoading ? (
              <div className="flex items-center gap-2 rounded-lg border border-forge-200 bg-forge-50 px-3 py-2.5 text-sm font-medium text-forge-800" role="status" aria-live="polite">
                <RefreshCw className="w-4 h-4 animate-spin shrink-0 text-forge-600" />
                {t('preview.loadingProducts')}
              </div>
            ) : products.length === 0 ? (
              <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-5 text-center">
                <p className="text-sm font-medium text-gray-900">{t('studio.emptyTitle')}</p>
                <p className="mt-1 text-xs text-gray-500 leading-relaxed">{t('studio.emptyBody')}</p>
                <Link
                  to="/products"
                  className="mt-3 inline-flex items-center justify-center rounded-lg bg-forge-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-forge-700 transition-colors"
                >
                  {t('studio.emptyCta')}
                </Link>
              </div>
            ) : (
              <select
                id="studio-product"
                value={selectedProduct}
                onChange={(e) => setSelectedProduct(e.target.value)}
                disabled={refreshing}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:opacity-50"
              >
                <option value="">{t('placeholders.studio.selectProduct')}</option>
                {products.map((product) => (
                  <option key={product.product_id} value={product.product_id}>
                    {product.product_name}
                  </option>
                ))}
              </select>
            )}
            {selectedProduct && (
              <p className="mt-2 text-xs text-gray-500">
                {t('studio.brandingMode', { mode: brandingModeLabel })}
              </p>
            )}
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <LabelWithTooltip
              label={t('fields.publishPlatforms')}
              tooltip={t('studio.tooltips.platforms')}
              required
            />
            <div className="flex flex-wrap gap-2 mt-1">
              {PLATFORMS.map((p) => {
                const selected = selectedPlatforms.includes(p);
                return (
                  <button
                    key={p}
                    onClick={() => togglePlatform(p)}
                    className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      selected
                        ? 'bg-forge-600 text-white shadow-md'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    <PlatformIcon
                      platform={p as PlatformId}
                      size={16}
                      variant={selected ? 'mono' : 'brand'}
                      className={selected ? 'text-white' : ''}
                    />
                    {platformLabel(p)}
                  </button>
                );
              })}
            </div>
          </div>

          <ImageGenerationControls
            showReferenceCount
            showCompareCreditHint={imageProviderMode === 'platform'}
            value={{
              use_scene_reference: useSceneReference,
              use_vision_image_prompt: useVisionImagePrompt,
              realistic_placement: realisticPlacement,
              reference_count: referenceCount,
              compare_scene_pipelines: compareScenePipelines,
            }}
            onChange={(next) => {
              setUseSceneReference(next.use_scene_reference);
              setUseVisionImagePrompt(next.use_vision_image_prompt);
              setRealisticPlacement(next.realistic_placement);
              setReferenceCount(next.reference_count);
              setCompareScenePipelines(next.compare_scene_pipelines ?? true);
              if (!next.use_scene_reference) {
                setCompareResults(null);
              }
            }}
            disabled={isGenerating}
          />

          <ImageModelPicker
            preferGlobalDefault
            value={{
              image_provider_id: imageProviderId,
              image_model: imageModel,
              image_size: imageSize,
              image_provider_mode: imageProviderMode,
            }}
            onChange={(next) => {
              setImageProviderId(next.image_provider_id ?? null);
              setImageModel(next.image_model ?? null);
              setImageSize(next.image_size ?? '2048x2048');
              setImageProviderMode(next.image_provider_mode ?? null);
            }}
            disabled={isGenerating}
          />

          <div className="space-y-3">
            <button
              onClick={() => handleGenerate('all')}
              disabled={generateActionsDisabled}
              title={t('studio.tooltips.generateAll')}
              className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-semibold transition-all ${
                generateActionsDisabled
                  ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  : 'bg-forge-600 text-white hover:bg-forge-700 shadow-sm'
              }`}
            >
              {isGenerating && generatingType === 'all' ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  {t('preview.generating')}
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  {t('preview.generateContent')}
                </>
              )}
            </button>

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => handleGenerate('copywriting')}
                disabled={generateActionsDisabled}
                title={t('studio.tooltips.generateCopy')}
                className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  generateActionsDisabled
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 hover:border-gray-400'
                }`}
              >
                {isGenerating && generatingType === 'copywriting' ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  </>
                ) : (
                  <>
                    <FileText className="w-4 h-4" />
                    {t('preview.generateCopyOnly')}
                  </>
                )}
              </button>

              <button
                onClick={() => handleGenerate('image')}
                disabled={generateActionsDisabled}
                title={t('studio.tooltips.generateImage')}
                className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  generateActionsDisabled
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 hover:border-gray-400'
                }`}
              >
                {isGenerating && generatingType === 'image' ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  </>
                ) : (
                  <>
                    <Image className="w-4 h-4" />
                    {t('preview.generateImageOnly')}
                  </>
                )}
              </button>
            </div>

            {generatedContent && (generatedContent.text || generatedContent.image) && (
              <button
                type="button"
                onClick={() => void handleSaveDraft()}
                disabled={isSavingDraft}
                className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isSavingDraft
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 hover:border-gray-400'
                }`}
              >
                {isSavingDraft ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    {t('preview.saving')}
                  </>
                ) : (
                  <>
                    <BookmarkPlus className="w-5 h-5" />
                    {t('preview.saveToPending')}
                  </>
                )}
              </button>
            )}

            {generatedContent && generatedContent.text && (
              <button
                onClick={handlePublish}
                disabled={isPublishing || selectedPlatforms.length === 0}
                className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isPublishing || selectedPlatforms.length === 0
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-gray-900 text-white hover:bg-gray-800 shadow-sm'
                }`}
              >
                {isPublishing ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    {t('preview.publishing')}
                  </>
                ) : (
                  <>
                    <Send className="w-5 h-5" />
                    {t('preview.publishTo', { platforms: selectedPlatforms.join(', ') })}
                  </>
                )}
              </button>
            )}
          </div>

          {isGenerating && pollHealth !== 'ok' && (
            <div
              className={`p-4 rounded-lg border ${
                pollHealth === 'stalled'
                  ? 'bg-orange-50 border-orange-200'
                  : 'bg-amber-50 border-amber-200'
              }`}
            >
              <p
                className={`text-sm font-medium ${
                  pollHealth === 'stalled' ? 'text-orange-800' : 'text-amber-800'
                }`}
              >
                {pollHealth === 'stalled'
                  ? t('preview.pollConnectionStalled')
                  : t('preview.pollConnectionDegraded')}
              </p>
              {pollHealth === 'stalled' && (
                <button
                  type="button"
                  onClick={() => void handleManualRefreshStatus()}
                  disabled={isRefreshingStatus}
                  className="mt-3 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-forge-600 text-white hover:bg-forge-700 disabled:opacity-60"
                >
                  <RefreshCw
                    className={`w-4 h-4 ${isRefreshingStatus ? 'animate-spin' : ''}`}
                  />
                  {isRefreshingStatus
                    ? t('preview.refreshingStatus')
                    : t('preview.refreshStatus')}
                </button>
              )}
            </div>
          )}

          {generateStatus && (
            <div className={`p-4 rounded-lg ${
              generateStatus.status === 'SUCCESS' ? 'bg-green-50' :
              generateStatus.status === 'FAILURE' ? 'bg-red-50' : 'bg-yellow-50'
            }`}>
              <p className={`font-medium ${
                generateStatus.status === 'SUCCESS' ? 'text-green-700' :
                generateStatus.status === 'FAILURE' ? 'text-red-700' : 'text-yellow-700'
              }`}>
                {generateStatus.status === 'SUCCESS' ? t('preview.generateSuccess') :
                 generateStatus.status === 'FAILURE' ? t('preview.generateError') : t('preview.processing')}
              </p>
              {generateStatus.status === 'FAILURE' && generateStatus.result?.error && (
                <p className="text-sm text-red-600 mt-1">
                  {sanitizeMessage(generateStatus.result.error, t('errors.generic'))}
                </p>
              )}
            </div>
          )}

          {generatedContent?.warning && (
            <div className="p-4 rounded-lg bg-amber-50 border border-amber-200">
              <p className="font-medium text-amber-800">
                {String(generatedContent.warning).includes('GitHub CDN')
                  ? t('pending.cdnFailed')
                  : generatedContent.warning_code === 'fidelity_placement'
                    ? t('preview.fidelityPlacement')
                    : generatedContent.warning_code === 'fidelity_branding'
                      ? t('preview.fidelityBranding')
                      : generatedContent.warning_code === 'fidelity_rendered'
                        ? t('preview.fidelityRendered')
                        : generatedContent.warning_code === 'fidelity_publish_paused'
                          ? t('preview.fidelityPublishPaused')
                          : generatedContent.warning_code === 'fidelity_product'
                            ? t('preview.fidelityProduct')
                            : generatedContent.warning_code === 'limited_reference'
                              ? t('preview.limitedReference')
                  : String(generatedContent.warning).includes('Unsupported product placement')
                    ? t('preview.fidelityPlacement')
                    : String(generatedContent.warning).includes('Branding could not be verified')
                      ? t('preview.fidelityBranding')
                      : String(generatedContent.warning).includes('heavily rendered')
                        ? t('preview.fidelityRendered')
                        : String(generatedContent.warning).includes('Automatic publishing paused')
                          ? t('preview.fidelityPublishPaused')
                          : String(generatedContent.warning).includes('Product details may differ')
                            ? t('preview.fidelityProduct')
                            : t('preview.qualityNotice')}
              </p>
              <p className="text-sm text-amber-700 mt-1">{generatedContent.warning}</p>
              {generatedContent.reference_diagnostics?.coverage && (
                <details className="mt-2 text-sm text-amber-800">
                  <summary>{t('preview.referenceDetails')}</summary>
                  <p className="mt-1">
                    {t('preview.referenceCoverage')}: {generatedContent.reference_diagnostics.coverage}
                    {compactSelectorReason(generatedContent.reference_diagnostics.reason, t)
                      ? ` · ${compactSelectorReason(generatedContent.reference_diagnostics.reason, t)}`
                      : ''}
                    {generatedContent.reference_diagnostics.diversity_applied
                      ? ` · ${t('preview.diversityRotated')}`
                      : ''}
                  </p>
                </details>
              )}
            </div>
          )}

          {generatedContent?.reference_diagnostics?.coverage && !generatedContent?.warning && (
            <details className="p-3 rounded-lg border border-slate-200 text-sm text-slate-600">
              <summary>{t('preview.referenceDetails')}</summary>
              <p className="mt-1">
                {t('preview.referenceCoverage')}: {generatedContent.reference_diagnostics.coverage}
                {compactSelectorReason(generatedContent.reference_diagnostics.reason, t)
                  ? ` · ${compactSelectorReason(generatedContent.reference_diagnostics.reason, t)}`
                  : ''}
                {generatedContent.reference_diagnostics.diversity_applied
                  ? ` · ${t('preview.diversityRotated')}`
                  : ''}
              </p>
            </details>
          )}

          {saveDraftStatus && (
            <div className={`p-4 rounded-lg flex items-center gap-2 ${
              saveDraftStatus === 'success' ? 'bg-green-50' : 'bg-red-50'
            }`}>
              {saveDraftStatus === 'success' ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="font-medium text-green-700">{t('preview.savedToPending')}</span>
                </>
              ) : (
                <span className="font-medium text-red-700">{t('preview.saveError')}</span>
              )}
            </div>
          )}

          {publishStatus && (
            <div className={`p-4 rounded-lg flex items-center gap-2 ${
              publishStatus === 'success' ? 'bg-green-50' : 'bg-red-50'
            }`}>
              {publishStatus === 'success' ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="font-medium text-green-700">{t('preview.publishSuccess')}</span>
                </>
              ) : (
                <>
                  <span className="font-medium text-red-700">{t('preview.publishFailed')}</span>
                </>
              )}
            </div>
          )}

          {generatedContent && (
            <ReferenceImagesDisplay
              productImages={generatedContent.reference_product_images}
              sceneImages={generatedContent.reference_scene_images}
              onPreview={setPreviewImage}
            />
          )}

          {comparePreviewActive ? (
            <div className="space-y-4">
              {(['legacy_scene', 'vision_scene'] as ScenePipelineKey[]).map((key) => {
                const slot = compareResults?.[key];
                if (!slot?.dimensions && !slot?.image_prompt) return null;
                return (
                  <div
                    key={key}
                    className={`border rounded-xl p-4 bg-white ${
                      activePipeline === key ? 'border-forge-400' : 'border-gray-200'
                    }`}
                  >
                    <p className="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">
                      {pipelineLabel(key)}
                    </p>
                    {slot.dimensions && !areDimensionsAllNull(slot.dimensions) && (
                      <DimensionInfoDisplay
                        dimensions={slot.dimensions}
                        diagnostics={slot.generation_diagnostics}
                      />
                    )}
                    {slot.image_prompt && (
                      <CopyablePromptBlock
                        label={t('fields.imagePrompt')}
                        text={slot.image_prompt}
                        className={
                          slot.dimensions && !areDimensionsAllNull(slot.dimensions)
                            ? 'mt-3'
                            : ''
                        }
                      />
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            generatedContent &&
            (generatedContent.dimensions || generatedContent.image_prompt) && (
              <div className="border-2 border-red-400 rounded-xl p-4 bg-white">
                {generatedContent.dimensions && (
                  <DimensionInfoDisplay
                    dimensions={generatedContent.dimensions}
                    diagnostics={generatedContent.generation_diagnostics}
                  />
                )}

                {generatedContent.image_prompt && (
                  <CopyablePromptBlock
                    label={t('fields.imagePrompt')}
                    text={generatedContent.image_prompt}
                    className={generatedContent.dimensions ? 'mt-3' : ''}
                  />
                )}
              </div>
            )
          )}
        </div>

        <div className="col-span-2">
          <div className="bg-white rounded-xl shadow-card border border-canvas-border p-6 min-h-[500px]">
            {comparePreviewActive ? (
              <div className="space-y-4">
                <div className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-gray-50 border border-gray-200">
                  <BrandAvatar
                    name={previewBrandName}
                    logoUrl={previewBrandLogo}
                    size="sm"
                    className="!rounded-full"
                  />
                  <div className="min-w-0">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">
                      {t('studio.compareSceneTitle')}
                    </p>
                    <p className="text-sm font-semibold text-gray-900 truncate">{previewBrandName}</p>
                  </div>
                </div>
                {generatedContent?.text && (
                  <p className="text-xs text-gray-500 text-center px-2">
                    {t('studio.compareSharedCaption')}
                  </p>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {renderComparePipelineCard(
                    'legacy_scene',
                    compareResults?.legacy_scene ?? null,
                  )}
                  {renderComparePipelineCard(
                    'vision_scene',
                    compareResults?.vision_scene ?? null,
                  )}
                </div>
              </div>
            ) : generatedContent && (generatedContent.image || generatedContent.text) ? (
              <div className="flex flex-col items-center">
                <div className="w-full max-w-sm mb-2 flex items-center gap-2.5 px-3 py-2 rounded-lg bg-gray-50 border border-gray-200">
                  <BrandAvatar
                    name={previewBrandName}
                    logoUrl={previewBrandLogo}
                    size="sm"
                    className="!rounded-full"
                  />
                  <div className="min-w-0">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">{t('studio.previewingAs')}</p>
                    <p className="text-sm font-semibold text-gray-900 truncate">{previewBrandName}</p>
                  </div>
                </div>
                <div className="w-full max-w-sm mb-6">
                  <SocialFeedPreview
                    platforms={selectedPlatforms}
                    image={generatedContent.image || undefined}
                    caption={generatedContent.text || undefined}
                    brandName={previewBrandName}
                    brandLogo={previewBrandLogo}
                    imageAlt={t('preview.generatedAlt')}
                    onImageClick={setPreviewImage}
                    isGenerating={isGenerating}
                    generatingType={generatingType}
                    generationProgress={generationProgress}
                    generationStage={generationStage}
                  />
                </div>
                {generatedContent.image && (
                  <GeneratedImagePanel
                    imageUrl={generatedContent.image}
                    imageAlt={t('preview.generatedAlt')}
                    onViewFullSize={setPreviewImage}
                    filename={`${previewBrandName.toLowerCase().replace(/[^a-z0-9]/g, '') || 'brand'}-generated.jpg`}
                  />
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center py-4">
                <div className="w-full max-w-sm mb-2 flex items-center gap-2.5 px-3 py-2 rounded-lg bg-gray-50 border border-gray-200">
                  <BrandAvatar
                    name={previewBrandName}
                    logoUrl={previewBrandLogo}
                    size="sm"
                    className="!rounded-full"
                  />
                  <div className="min-w-0">
                    <p className="text-[10px] text-gray-500 uppercase tracking-wide">{t('studio.previewingAs')}</p>
                    <p className="text-sm font-semibold text-gray-900 truncate">{previewBrandName}</p>
                  </div>
                </div>
                <div className="w-full max-w-sm">
                  <SocialFeedPreview
                    platforms={selectedPlatforms.length > 0 ? selectedPlatforms : ['instagram']}
                    caption={t('preview.selectAndGenerate')}
                    brandName={previewBrandName}
                    brandLogo={previewBrandLogo}
                    imageAlt={t('preview.generatedAlt')}
                    isGenerating={isGenerating}
                    generatingType={generatingType}
                    generationProgress={generationProgress}
                    generationStage={generationStage}
                  />
                </div>
                {!isGenerating && (
                  <p className="mt-6 text-sm text-ink-500 text-center max-w-md">
                    {t('preview.previewArea')}. {t('preview.selectAndGenerate')}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {previewImage && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center z-50"
          onClick={() => setPreviewImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] p-4 flex flex-col items-center">
            <button
              type="button"
              onClick={() => setPreviewImage(null)}
              className="absolute top-2 right-2 text-white hover:text-gray-300 z-10"
            >
              <X className="w-8 h-8" />
            </button>
            <img
              src={previewImage}
              alt={t('preview.referencePreviewAlt')}
              className="max-w-full max-h-[80vh] object-contain rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                void downloadImage(
                  previewImage,
                  `${previewBrandName.toLowerCase().replace(/[^a-z0-9]/g, '') || 'image'}.jpg`
                );
              }}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white/95 text-gray-900 text-sm font-medium hover:bg-white"
            >
              <Download className="w-4 h-4" />
              {t('preview.downloadImage')}
            </button>
          </div>
        </div>
      )}

      <PublishProgressOverlay
        open={publishOverlay.open}
        phase={publishOverlay.phase}
        platforms={publishOverlay.platforms}
      />
    </div>
  );
}