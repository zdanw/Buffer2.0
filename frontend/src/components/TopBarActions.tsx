import { SubscribeCreditsButton } from '@/components/SubscribeCreditsModal';
import UserAccountMenu from '@/components/UserAccountMenu';

/** Global account actions shown in the app chrome header (upgrade + profile). */
export default function TopBarActions() {
  return (
    <div className="flex shrink-0 items-center gap-2.5">
      <SubscribeCreditsButton variant="inline" />
      <UserAccountMenu />
    </div>
  );
}
