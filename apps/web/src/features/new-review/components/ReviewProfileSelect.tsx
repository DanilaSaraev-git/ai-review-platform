import type { ReviewProfile } from '@/api/generated/model';
import { RadioCards } from '@/components/ui';

/**
 * Выбор профиля проверки с назначением и версией (FR-009).
 * В запуск отправляется пара {id, version}: версия участвует в
 * воспроизводимости результата (FR-017).
 */
export function ReviewProfileSelect({
  profiles,
  selectedId,
  onSelect,
}: {
  profiles: readonly ReviewProfile[];
  selectedId: string | undefined;
  onSelect: (profile: ReviewProfile) => void;
}) {
  return (
    <RadioCards
      legend="Профиль проверки"
      name="review-profile"
      value={selectedId}
      onValueChange={(value) => {
        const found = profiles.find((profile) => profile.id === value);
        if (found) {
          onSelect(found);
        }
      }}
      options={profiles.map((profile) => ({
        value: profile.id,
        label: `${profile.name} · версия ${profile.version}`,
        description: profile.goal,
      }))}
    />
  );
}
