import type { ReviewProfile } from '@/api/generated/model';
import { useId } from 'react';
import { Icon } from '@/components/ui/Icon';

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
  const id = useId();
  return (
    <div className="entry-setting-group">
      <div className="entry-setting">
        <label htmlFor={id} className="entry-setting-label"><Icon name="layers" />Профиль проверки</label>
        <select
          id={id}
          name="review-profile"
          value={selectedId ?? ''}
          onChange={(event) => {
            const found = profiles.find((profile) => profile.id === event.target.value);
            if (found) onSelect(found);
          }}
        >
          {!selectedId ? <option value="" disabled>Выберите профиль</option> : null}
          {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name} · версия {profile.version}</option>)}
        </select>
      </div>
    </div>
  );
}
