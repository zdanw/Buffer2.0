import { mergeLocale, sharedEn } from './shared';
import { pagesEn } from './pages';
import { en as baseEn } from './en.base';
import { placeholdersEn } from './placeholders';

export const en = mergeLocale(baseEn, sharedEn, pagesEn, placeholdersEn);
