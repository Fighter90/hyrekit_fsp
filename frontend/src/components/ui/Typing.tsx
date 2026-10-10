import { useEffect, useState } from 'react'
import { prefersReducedMotion } from '../../hooks/useReveal'

interface Props {
  words: string[]
  typeMs?: number
  holdMs?: number
}

/** Эффект печати с мигающим курсором: слова печатаются и стираются по кругу. */
export default function Typing({ words, typeMs = 70, holdMs = 1600 }: Props) {
  const [i, setI] = useState(0)
  const [len, setLen] = useState(0)
  const [deleting, setDeleting] = useState(false)
  const reduced = prefersReducedMotion()
  const word = words[i % words.length] ?? ''

  useEffect(() => {
    if (reduced) return
    let t: ReturnType<typeof setTimeout>
    if (!deleting && len < word.length) t = setTimeout(() => setLen(len + 1), typeMs)
    else if (!deleting && len === word.length) t = setTimeout(() => setDeleting(true), holdMs)
    else if (deleting && len > 0) t = setTimeout(() => setLen(len - 1), typeMs / 2)
    else {
      t = setTimeout(() => {
        setDeleting(false)
        setI((x) => x + 1)
      }, 200)
    }
    return () => clearTimeout(t)
  }, [len, deleting, word, typeMs, holdMs, reduced])

  return (
    <span className="typing">
      <span className="typing__text">{reduced ? words[0] : word.slice(0, len)}</span>
      <span className="typing__cursor" aria-hidden>_</span>
      <span className="sr-only">{words.join(', ')}</span>
    </span>
  )
}
