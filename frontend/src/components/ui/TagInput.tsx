import { useId, useState, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { normalizeTag } from '../../lib/format'

interface Props {
  value: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
  suggestions?: string[]
  id?: string
  max?: number
}

/** Ввод тегов: Enter / запятая добавляют, Backspace на пустом поле удаляет последний. */
export default function TagInput({ value, onChange, placeholder = 'Введите и нажмите Enter', suggestions = [], id, max = 40 }: Props) {
  const [draft, setDraft] = useState('')
  const listId = useId()

  const add = (raw: string) => {
    const parts = raw.split(',').map(normalizeTag).filter(Boolean)
    if (!parts.length) return
    const lower = new Set(value.map((v) => v.toLowerCase()))
    const next = [...value]
    for (const p of parts) {
      if (!lower.has(p.toLowerCase()) && next.length < max) {
        next.push(p)
        lower.add(p.toLowerCase())
      }
    }
    onChange(next)
    setDraft('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      add(draft)
    } else if (e.key === 'Backspace' && !draft && value.length) {
      onChange(value.slice(0, -1))
    }
  }

  const free = suggestions.filter((s) => !value.some((v) => v.toLowerCase() === s.toLowerCase()))

  return (
    <div className="tag-input">
      <div className="tag-input__box">
        {value.map((t) => (
          <span key={t} className="tag tag--removable">
            {t}
            <button type="button" onClick={() => onChange(value.filter((x) => x !== t))} aria-label={`Удалить ${t}`}>
              <X size={12} />
            </button>
          </span>
        ))}
        <input
          id={id}
          className="tag-input__field"
          value={draft}
          placeholder={value.length ? '' : placeholder}
          onChange={(e) => {
            const v = e.target.value
            if (v.includes(',')) add(v)
            else setDraft(v)
          }}
          onKeyDown={onKeyDown}
          onBlur={() => draft && add(draft)}
          list={free.length ? listId : undefined}
        />
      </div>
      {free.length > 0 && (
        <>
          <datalist id={listId}>
            {free.map((s) => <option key={s} value={s} />)}
          </datalist>
          <div className="tag-input__suggest">
            {free.slice(0, 8).map((s) => (
              <button type="button" key={s} className="chip-btn" onClick={() => add(s)}>
                + {s}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
