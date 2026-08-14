import { mergeLocale, sharedEn } from './shared';
import { pagesEn } from './pages';
import { en as baseEn } from './en.base';

export const en = mergeLocale(baseEn, sharedEn, pagesEn);
