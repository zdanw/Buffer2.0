import { SubscribeCreditsButton } from '@/components/SubscribeCreditsModal';
import TopBarHelpLink from '@/components/TopBarHelpLink';
import UserAccountMenu from '@/components/UserAccountMenu';

/** Global chrome: help, upgrade, and account menu. */
export default function TopBarActions() {
  return (
    <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
      <TopBarHelpLink />
      <SubscribeCreditsButton variant="inline" />
      <UserAccountMenu />
    </div>
  );
}
