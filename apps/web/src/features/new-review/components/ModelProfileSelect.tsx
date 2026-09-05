import type { ModelProfile } from '@/api/generated/model';
import { RadioCards } from '@/components/ui';

/**
 * Выбор профиля модели (FR-010).
 * Профиль с availability = unavailable невыбираем, и рядом названа причина:
 * неактивный элемент без объяснения оставляет аналитика в неведении.
 */
export function ModelProfileSelect({
  profiles,
  selectedId,
  onSelect,
}: {
  profiles: readonly ModelProfile[];
  selectedId: string | undefined;
  onSelect: (profile: ModelProfile) => void;
}) {
  return (
    <RadioCards
      legend="Профиль модели"
      name="model-profile"
      value={selectedId}
      onValueChange={(value) => {
        const found = profiles.find((profile) => profile.id === value && profile.availability === 'available');
        if (found) {
          onSelect(found);
        }
      }}
      options={profiles.map((profile) => ({
        value: profile.id,
        label: `${profile.name} · версия ${profile.version}`,
        description: profile.description,
        disabled: profile.availability === 'unavailable',
        disabledReason:
          profile.availability === 'unavailable' ? 'Профиль недоступен, выбрать его сейчас нельзя.' : undefined,
      }))}
    />
  );
}
