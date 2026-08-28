/** Studio caps product reference images at 4 per generation. */
export const STUDIO_REFERENCE_COUNT_MAX = 4;

/** Shared image-generation toggles used by Studio and Task Configuration. */
export interface ImageGenerationControlValues {
  use_scene_reference: boolean;
  use_vision_image_prompt: boolean;
  realistic_placement: boolean;
  reference_count: number;
  compare_scene_pipelines?: boolean;
}

export const DEFAULT_IMAGE_GENERATION_CONTROLS: ImageGenerationControlValues = {
  use_scene_reference: false,
  use_vision_image_prompt: false,
  realistic_placement: true,
  reference_count: 2,
  compare_scene_pipelines: true,
};
