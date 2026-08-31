import type { TranslationTree } from '../types';
import { mergeLocale, sharedZh } from './shared';
import { pagesZh } from './pages';
import { zh as baseZh } from './zh.base';
import { placeholdersZh } from './placeholders';
import { guidesZh } from './guides';

export const zh: TranslationTree = mergeLocale(baseZh, sharedZh, pagesZh, placeholdersZh, guidesZh);
