import { CURRENCY_OPTIONS, currencySymbol } from '../../lib/constants';
import { formatIndianCurrencyInput } from '../../lib/currencyInput';

/**
 * Money input with a currency symbol and live Indian digit grouping
 * (10,000 / 1,00,000) via lib/currencyInput. Holds the FORMATTED string in
 * its value; call-sites convert with parseIndianCurrencyInput() before
 * submitting. When a `currency` + `onCurrencyChange` are provided, a compact
 * currency selector (INR/USD/EUR/…) is rendered beside the amount field.
 */
export default function CurrencyInput({
  value,
  onChange,
  placeholder = '0',
  disabled = false,
  required = false,
  compact = false,
  className = '',
  currency = 'INR',
  onCurrencyChange,
}: {
  value: string;
  onChange: (formatted: string) => void;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  compact?: boolean;
  className?: string;
  currency?: string;
  onCurrencyChange?: (code: string) => void;
}) {
  const hasSelector = !!onCurrencyChange;
  return (
    <div className={`relative ${className}`}>
      {!hasSelector && (
        <span
          aria-hidden="true"
          className={`pointer-events-none absolute top-1/2 -translate-y-1/2 font-medium text-muted ${
            compact ? 'left-2 text-xs' : 'left-3 text-sm'
          }`}
        >
          {currencySymbol(currency)}
        </span>
      )}
      {hasSelector && (
        <select
          aria-label="Currency"
          value={currency}
          onChange={(e) => onCurrencyChange(e.target.value)}
          disabled={disabled}
          className={`absolute top-1/2 -translate-y-1/2 border-0 bg-transparent font-medium text-muted focus:outline-none ${
            compact ? 'left-1 text-[11px]' : 'left-1.5 text-xs'
          }`}
        >
          {CURRENCY_OPTIONS.map((c) => (
            <option key={c.code} value={c.code}>
              {c.symbol}
            </option>
          ))}
        </select>
      )}
      <input
        type="text"
        inputMode="numeric"
        required={required}
        disabled={disabled}
        value={value}
        onChange={(e) => onChange(formatIndianCurrencyInput(e.target.value))}
        placeholder={placeholder}
        className={`w-full rounded-md border border-border bg-surface text-ink shadow-card transition placeholder:text-muted/70 hover:border-graphite/40 focus:border-navy focus:outline-none focus:ring-2 focus:ring-navy/30 disabled:cursor-not-allowed disabled:bg-surfaceWarm/50 disabled:opacity-70 ${
          compact
            ? 'h-8 pl-6 pr-2 text-xs'
            : hasSelector
              ? 'h-10 pl-8 pr-3 text-sm'
              : 'h-10 pl-7 pr-3 text-sm'
        }`}
      />
    </div>
  );
}
