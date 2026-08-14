import type { TranslationTree } from '../types';
import { mergeLocale, sharedZh } from './shared';
import { pagesZh } from './pages';
import { zh as baseZh } from './zh.base';

export const zh: TranslationTree = mergeLocale(baseZh, sharedZh, pagesZh);
