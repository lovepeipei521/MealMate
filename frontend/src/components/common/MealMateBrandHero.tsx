import { Utensils } from 'lucide-react';

export function MealMateBrandHero() {
  return (
    <div className="mm-empty-brand" aria-label="MealMate">
      <div className="mm-empty-brand-mark">
        <Utensils aria-hidden="true" />
      </div>
      <div>
        <div className="mm-empty-brand-name">MealMate</div>
        <div className="mm-empty-brand-sub">KITCHEN NOTES</div>
      </div>
    </div>
  );
}
