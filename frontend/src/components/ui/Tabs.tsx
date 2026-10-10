interface Tab<K extends string> {
  key: K
  label: string
  count?: number
}

interface Props<K extends string> {
  tabs: Tab<K>[]
  value: K
  onChange: (k: K) => void
}

export default function Tabs<K extends string>({ tabs, value, onChange }: Props<K>) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={t.key === value}
          className={`tabs__tab ${t.key === value ? 'is-active' : ''}`}
          onClick={() => onChange(t.key)}
        >
          {t.label}
          {t.count !== undefined && <span className="tabs__count">{t.count}</span>}
        </button>
      ))}
    </div>
  )
}
