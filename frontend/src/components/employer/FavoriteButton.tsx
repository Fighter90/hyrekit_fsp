import { useState } from 'react'
import { Bookmark, BookmarkCheck } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import { errorMessage } from '../../lib/format'

interface Props {
  profileId: string
  initial: boolean
  vacancyId?: string
  onChange?: (value: boolean) => void
}

/** Добавить кандидата в шортлист компании или убрать из него. */
export default function FavoriteButton({ profileId, initial, vacancyId, onChange }: Props) {
  const toast = useToast()
  const [on, setOn] = useState(initial)
  const [busy, setBusy] = useState(false)

  const toggle = async () => {
    setBusy(true)
    try {
      if (on) await api.removeFavorite(profileId)
      else await api.addFavorite(profileId, { vacancy_id: vacancyId ?? null })
      setOn(!on)
      onChange?.(!on)
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось обновить избранное'))
    } finally {
      setBusy(false)
    }
  }

  const label = on ? 'Убрать из избранного' : 'В избранное'
  return (
    <button
      type="button"
      className={`icon-btn fav-btn ${on ? 'is-on' : ''}`}
      aria-pressed={on}
      aria-label={label}
      title={label}
      disabled={busy}
      onClick={() => void toggle()}
    >
      {on ? <BookmarkCheck size={17} /> : <Bookmark size={17} />}
    </button>
  )
}
