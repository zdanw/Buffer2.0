export const HERO_TITLE_KEYS = [
  'landing.heroTitle1',
  'landing.heroTitle2',
  'landing.heroTitle3',
  'landing.heroTitle4',
  'landing.heroTitle5',
] as const;

export type HeroTitleKey = (typeof HERO_TITLE_KEYS)[number];

export function pickRandomHeroTitleKey(): HeroTitleKey {
  return HERO_TITLE_KEYS[Math.floor(Math.random() * HERO_TITLE_KEYS.length)];
}
