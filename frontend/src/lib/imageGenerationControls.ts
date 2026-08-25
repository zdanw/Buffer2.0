/** Shared image-generation toggles used by Studio and Task Configuration. */
export interface ImageGenerationControlValues {
  use_scene_reference: boolean;
  use_vision_image_prompt: boolean;
  realistic_placement: boolean;
}

export const DEFAULT_IMAGE_GENERATION_CONTROLS: ImageGenerationControlValues = {
  use_scene_reference: false,
  use_vision_image_prompt: false,
  realistic_placement: true,
};
