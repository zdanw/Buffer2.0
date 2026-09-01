import { useState } from 'react';
import { Check, Copy, ZoomIn } from 'lucide-react';
import type { GenerationHistoryDetail } from '@/api/generationHistory';
import type { DimensionInfo } from '@/api/generate';
import ReferenceImagesDisplay from '@/components/ReferenceImagesDisplay';
import DimensionInfoDisplay, { CopyablePromptBlock } from '@/components/DimensionInfoDisplay';
import { useI18n } from '@/i18n/useI18n';
import { formatServerDateTime } from '@/lib/datetime';
import { refsFromManifest } from '@/lib/generationHistoryUtils';

function statusClass(status: string): string {
  switch (status) {
    case 'succeeded':
      return 'bg-green-100 text-green-800';
    case 'failed':
      return 'bg-red-100 text-red-800';
    case 'pending':
    case 'running':
      return 'bg-yellow-100 text-yellow-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

function severityClass(severity: string): string {
  switch (severity) {
    case 'hard_fail':
      return 'bg-red-100 text-red-800';
    case 'warning':
      return 'bg-amber-100 text-amber-800';
    default:
      return 'bg-gray-100 text-gray-700';
  }
}

function stageLabel(stage: string, t: (key: string) => string): string {
  if (stage === 'pre_generation') return t('generationHistory.stagePreGeneration');
  if (stage === 'post_generation') return t('generationHistory.stagePostGeneration');
  if (stage === 'publish_gate') return t('generationHistory.stagePublishGate');
  return stage;
}

function CopyableRunId({ runId }: { runId: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(runId);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          {t('generationHistory.runId')}
        </p>
        <p className="text-xs font-mono text-gray-800 truncate">{runId}</p>
      </div>
      <button
        type="button"
        onClick={() => void handleCopy()}
        className="shrink-0 inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100"
      >
        {copied ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
        {t('common.copy')}
      </button>
    </div>
  );
}

interface GenerationRunDetailProps {
  detail: GenerationHistoryDetail | null;
  loading: boolean;
}

export default function GenerationRunDetail({ detail, loading }: GenerationRunDetailProps) {
  const { t, locale } = useI18n();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-forge-600" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-gray-500">
        {t('generationHistory.selectRun')}
      </div>
    );
  }

  const snapshot = detail.output_snapshot || {};
  const imagePrompt =
    snapshot.image_prompt ||
    (typeof detail.generate_task?.result?.image_prompt === 'string'
      ? detail.generate_task.result.image_prompt
      : '');
  const copywriting =
    snapshot.copywriting ||
    (typeof detail.generate_task?.result?.text === 'string' ? detail.generate_task.result.text : '');
  const dimensions = snapshot.dimensions || detail.generate_task?.result?.dimensions;

  const manifestRefs = refsFromManifest(detail.reference_manifest);
  const productRefs =
    snapshot.reference_product_images?.length
      ? snapshot.reference_product_images
      : Array.isArray(detail.generate_task?.result?.reference_product_images)
        ? (detail.generate_task.result.reference_product_images as string[])
        : manifestRefs.product;
  const sceneRefs =
    snapshot.reference_scene_images?.length
      ? snapshot.reference_scene_images
      : Array.isArray(detail.generate_task?.result?.reference_scene_images)
        ? (detail.generate_task.result.reference_scene_images as string[])
        : manifestRefs.scene;

  const promptMessage = (() => {
    if (imagePrompt) return null;
    if (detail.generate_task?.expired) {
      return t('generationHistory.promptExpired');
    }
    if (!detail.output_snapshot && detail.status === 'succeeded') {
      return t('generationHistory.promptPreMigration');
    }
    return t('generationHistory.promptUnavailable');
  })();

  const heroImage = detail.artifacts[0]?.cdn_url;

  return (
    <div className="space-y-5">
      <CopyableRunId runId={detail.run_id} />

      {detail.artifacts.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('generationHistory.outputImages')}</h3>
          {heroImage ? (
            <button
              type="button"
              onClick={() => setPreviewUrl(heroImage)}
              className="relative group w-full rounded-xl overflow-hidden border border-gray-200 mb-3"
            >
              <img src={heroImage} alt="" className="w-full max-h-80 object-contain bg-gray-50" />
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                <ZoomIn className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 drop-shadow" />
              </div>
            </button>
          ) : null}
          {detail.artifacts.length > 1 ? (
            <div className="grid grid-cols-2 gap-3">
              {detail.artifacts.slice(1).map((artifact) => (
                <button
                  key={artifact.artifact_id}
                  type="button"
                  onClick={() => setPreviewUrl(artifact.cdn_url)}
                  className={`relative group rounded-lg overflow-hidden border ${
                    artifact.selected ? 'border-forge-600 ring-2 ring-forge-200' : 'border-gray-200'
                  }`}
                >
                  <img src={artifact.cdn_url} alt="" className="w-full h-28 object-cover" />
                  {artifact.selected ? (
                    <span className="absolute top-2 left-2 text-[10px] font-medium bg-forge-600 text-white px-2 py-0.5 rounded">
                      {t('generationHistory.selected')}
                    </span>
                  ) : null}
                </button>
              ))}
            </div>
          ) : null}
          {detail.artifacts.some((a) => a.selected) ? (
            <p className="text-[11px] text-gray-500 mt-2">{t('generationHistory.selectedArtifactHint')}</p>
          ) : null}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-center">
          <p className="text-sm text-gray-600">{t('generationHistory.noOutputImages')}</p>
          {detail.status === 'failed' ? (
            <p className="text-xs text-gray-500 mt-1">{t('generationHistory.noOutputFailedHint')}</p>
          ) : null}
        </div>
      )}

      <div className="rounded-lg border border-forge-200 bg-forge-50 px-4 py-3 text-sm text-forge-900">
        {detail.diagnosis_line}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
        <span className={`inline-flex px-2.5 py-0.5 rounded-full font-medium ${statusClass(detail.status)}`}>
          {detail.status}
        </span>
        <span>{detail.source}</span>
        <span>{formatServerDateTime(detail.created_at, locale, t('datetime.unknown'))}</span>
        {detail.user ? (
          <span>
            {detail.user.username} ({detail.user.email})
          </span>
        ) : null}
        {detail.product ? <span>{detail.product.name}</span> : null}
      </div>

      {imagePrompt ? (
        <CopyablePromptBlock label={t('fields.imagePrompt')} text={imagePrompt} />
      ) : (
        <p className="text-xs text-gray-500 italic">{promptMessage}</p>
      )}

      {copywriting ? (
        <CopyablePromptBlock label={t('fields.copyContent')} text={copywriting} />
      ) : null}

      {dimensions && typeof dimensions === 'object' ? (
        <DimensionInfoDisplay dimensions={dimensions as unknown as DimensionInfo} />
      ) : null}

      <ReferenceImagesDisplay
        productImages={productRefs}
        sceneImages={sceneRefs}
        onPreview={setPreviewUrl}
      />

      {detail.quality_findings.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('generationHistory.qaFindings')}</h3>
          <div className="space-y-2">
            {detail.quality_findings.map((finding) => (
              <div
                key={finding.finding_id}
                className="rounded-lg border border-gray-100 bg-white px-3 py-2 text-xs"
              >
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span
                    className={`inline-flex px-2 py-0.5 rounded-full font-medium ${severityClass(finding.severity)}`}
                  >
                    {finding.severity}
                  </span>
                  <span className="text-gray-500">{stageLabel(finding.stage, t)}</span>
                  <span className="font-medium text-gray-800">{finding.check_label}</span>
                </div>
                {!finding.passed && finding.details ? (
                  <pre className="text-[10px] text-gray-600 whitespace-pre-wrap break-words">
                    {JSON.stringify(finding.details, null, 2)}
                  </pre>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
          <h4 className="font-semibold text-gray-700 mb-2">{t('generationHistory.creditsSection')}</h4>
          <p>{t('generationHistory.creditsCharged', { n: detail.credit.charged })}</p>
          {detail.credit.reservation_status ? (
            <p>{t('generationHistory.reservationStatus', { status: detail.credit.reservation_status })}</p>
          ) : null}
          {detail.credit.grant_source ? (
            <p>{t('generationHistory.grantSource', { source: detail.credit.grant_source })}</p>
          ) : null}
        </div>
        <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
          <h4 className="font-semibold text-gray-700 mb-2">{t('generationHistory.pipelineSection')}</h4>
          <p>{detail.executed_pipeline_version}</p>
          {detail.model ? <p>{detail.model}</p> : null}
          {detail.image_provider_mode ? <p>{detail.image_provider_mode}</p> : null}
          {detail.latency_ms != null ? (
            <p>{t('generationHistory.latency', { ms: detail.latency_ms })}</p>
          ) : null}
        </div>
      </div>

      {detail.error_category || snapshot.error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {detail.error_category ? <p>{detail.error_category}</p> : null}
          {snapshot.error ? <p>{snapshot.error}</p> : null}
        </div>
      ) : null}

      {snapshot.warning ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {snapshot.warning}
        </div>
      ) : null}

      {detail.compare_siblings.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('generationHistory.compareSiblings')}</h3>
          <div className="space-y-2">
            {detail.compare_siblings.map((sibling) => (
              <div
                key={sibling.run_id}
                className="flex items-center gap-3 text-xs border border-gray-100 rounded-lg p-2"
              >
                {sibling.thumbnail_url ? (
                  <img src={sibling.thumbnail_url} alt="" className="w-12 h-12 object-cover rounded" />
                ) : null}
                <div>
                  <p className="font-mono text-[10px] text-gray-500">{sibling.run_id}</p>
                  <p>{sibling.image_prompt_pipeline || sibling.status}</p>
                  {sibling.selected ? (
                    <span className="text-forge-700 font-medium">{t('generationHistory.selected')}</span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <details className="rounded-lg border border-gray-100 bg-white">
        <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-gray-700">
          {t('generationHistory.technicalJson')}
        </summary>
        <div className="px-3 pb-3 space-y-3">
          {detail.generation_plan ? (
            <pre className="text-[10px] overflow-x-auto bg-gray-50 p-2 rounded max-h-64">
              {JSON.stringify(detail.generation_plan, null, 2)}
            </pre>
          ) : null}
          {detail.reference_manifest ? (
            <pre className="text-[10px] overflow-x-auto bg-gray-50 p-2 rounded max-h-48">
              {JSON.stringify(detail.reference_manifest, null, 2)}
            </pre>
          ) : null}
        </div>
      </details>

      {previewUrl ? (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setPreviewUrl(null)}
          onKeyDown={(e) => e.key === 'Escape' && setPreviewUrl(null)}
          role="button"
          tabIndex={0}
        >
          <img
            src={previewUrl}
            alt=""
            className="max-w-full max-h-full object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      ) : null}
    </div>
  );
}
