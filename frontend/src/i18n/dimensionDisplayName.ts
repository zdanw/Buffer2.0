import type { Locale } from '@/i18n/types';

const DEFAULT_DIM_LABELS_EN: Record<string, string> = {
  默认场景: 'Default scene',
  默认光线: 'Default lighting',
  默认风格: 'Default style',
  默认细节: 'Default details',
  默认视角: 'Default viewpoint',
  默认构图: 'Default composition',
  默认画质: 'Default quality',
};

const ITEM_LABELS_EN: Record<string, string> = {
  nursery: 'Cozy nursery corner',
  bedside: 'Dim bedside at night',
  stroller: 'Stroller walk in the park',
  nightstand: 'Nightstand with feeding items',
  hotel: 'Travel hotel room',
  livingroom: 'Living room play mat',
  nursing: 'Nursing chair at night',
  carseat: 'Car seat mount',
  bedside_night: 'Master bedroom nightstand',
  stroller_outdoor: 'Outdoor stroller walk',
  nightstand_nursery: 'Nursery nightstand',
  hotel_travel: 'Travel hotel room',
  livingroom_play: 'Living room play mat',
  nursing_chair: 'Nursing chair at night',
  car_travel: 'Car travel',
  kitchen_housework: 'Kitchen while cooking',
  bedroom_parent: 'Master bedroom nightstand',
  livingroom_family: 'Family living room',
  baby_play: 'Baby play mat area',
  home_office: 'Home office desk',
  kitchen_area: 'Open kitchen dining area',
  eye_level: 'Eye-level 45° product close-up',
  top_down: 'Top-down flat lay',
  low_angle: 'Low baby-eye angle',
  selfie: 'Parent selfie POV',
  side_view: 'Side profile view',
  macro: 'Macro detail close-up',
  pov: 'Stroller handle POV',
  eye_level_45: '45° eye-level close-up',
  top_down_flatlay: 'Top-down flat lay',
  baby_low_angle: 'Low baby-eye angle',
  parent_selfie: 'Parent selfie POV',
  side_profile: 'Side profile view',
  macro_detail: 'Macro detail close-up',
  pov_kitchen: 'Kitchen POV',
  dual_hand_hold: 'Dual-hand product hold',
  pov_livingroom: 'Living room POV',
  dual_product: 'Two products side by side',
  camera_pov: 'Camera POV from above crib',
  parent_view_screen: 'Parent monitor screen view',
  dual_screen: 'Dual-screen display',
  rule_of_thirds: 'Rule of thirds',
  symmetry: 'Center symmetry',
  foreground_blur: 'Foreground blur through crib rails',
  diagonal: 'Diagonal leading line',
  full_frame: 'Full-frame color gradient',
  minimalist: 'Minimal white space',
  narrative: 'Narrative lifestyle frame',
  symmetry_dual: 'Dual-product symmetry',
  symmetry_center: 'Center symmetry',
  foreground_blur_crib: 'Foreground blur through crib rails',
  diagonal_guide: 'Diagonal narrative guide',
  diagonal_flow: 'Diagonal airflow flow',
  minimal_white_space: 'Minimal white space',
  narrative_lifestyle: 'Narrative lifestyle frame',
  layer_depth: 'Foreground/background depth layers',
  nordic: 'Nordic minimalist baby aesthetic',
  documentary: 'Warm documentary film look',
  dreamy: 'Soft dreamy bokeh',
  lifestyle: 'Real lifestyle photography',
  nordic_minimal: 'Nordic minimalist aesthetic',
  warm_documentary: 'Warm documentary film look',
  soft_dreamy: 'Soft dreamy bokeh',
  real_lifestyle: 'Real lifestyle photography',
  commercial_clean: 'Clean commercial product shot',
  '8k': '8K ultra detail',
  cinematic: 'Cinematic depth of field',
  c4d: 'C4D render quality',
  macro_photo: 'Macro product photography',
  hdr: 'HDR high dynamic range',
  '8k_ultra': '8K ultra detail',
  cinematic_depth: 'Cinematic depth of field',
  c4d_render: 'C4D render quality',
  macro_pro_photo: 'Macro product photography',
  hdr_high_dynamic: 'HDR high dynamic range',
  toys: 'Organic cotton toys and knit blanket',
  book: 'Cloth book and wooden rattle',
  feeding: 'Warm bottle and swaddle',
  decor: 'Star-moon decor and fiddle-leaf fig',
  baby_parts: 'Baby hands or feet (no face)',
  music: 'Scattered music note paper art',
  monitor: 'Thermometer and baby monitor',
  nursery_toys: 'Knit comfort toys and blanket',
  baby_gear: 'Cloth book, pacifier, storage basket',
  night_supplies: 'Night feeding and skincare items',
  travel_baby_bag: 'Travel diaper bag',
  baby_part_detail: 'Baby hands or feet (no face)',
  household_scene: 'Kitchen and living room props',
  green_plants: 'Indoor greenery decor',
  travel_bag: 'Travel bag and charging cable',
  home_decor: 'Candles, art prints, throw pillows',
  product_glow: 'Product glow as only light source',
  morning: 'Soft morning window light',
  backlight: 'Golden rim backlight',
  table_lamp: 'Warm bedside lamp sidelight',
  darkness: 'Dark room with soft product glow',
  golden_hour: 'Golden hour through curtains',
  screen_soft_glow: 'Soft monitor screen glow',
  morning_window_light: 'Soft morning window light',
  gold_edge_backlight: 'Golden rim backlight',
  bedside_table_lamp: 'Warm bedside lamp sidelight',
  dim_night_ambient: 'Dim night ambient glow',
  golden_hour_diffuse: 'Golden hour diffuse light',
  soft_night_glow: 'Soft night indicator glow',
  infrared_night: 'Infrared night-vision glow',
  default: 'Default',
};

function slugToEnglish(itemId: string): string {
  const value = itemId.trim();
  if (!value || value === 'default') return 'Default';
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function lookupEnglishDimensionName(
  itemId: string | undefined,
  nameZh?: string,
  nameEn?: string | null,
): string {
  const explicit = (nameEn || '').trim();
  if (explicit) return explicit;
  const key = (itemId || '').trim();
  if (key && ITEM_LABELS_EN[key]) return ITEM_LABELS_EN[key];
  if (key) return slugToEnglish(key);
  return (nameZh || '').trim() || 'Default';
}

export function getDimensionDisplayName(
  item: { name?: string | null; name_en?: string | null; item_id?: string | null; id?: string | null },
  locale: Locale,
): string {
  const name = (item.name || '').trim();
  const itemId = (item.item_id || item.id || '').trim();
  if (locale === 'zh') {
    return name || '默认';
  }
  if (name && DEFAULT_DIM_LABELS_EN[name]) {
    return DEFAULT_DIM_LABELS_EN[name];
  }
  const english = lookupEnglishDimensionName(itemId, name, item.name_en);
  if (english) return english;
  if (name && !/[\u4e00-\u9fff]/.test(name)) return name;
  return 'Default';
}
