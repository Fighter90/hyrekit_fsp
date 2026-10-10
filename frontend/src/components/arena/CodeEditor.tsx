import { useEffect, useRef } from 'react'
import { EditorView, basicSetup } from 'codemirror'
import { EditorState, Compartment } from '@codemirror/state'
import { keymap } from '@codemirror/view'
import { indentWithTab } from '@codemirror/commands'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { oneDark } from '@codemirror/theme-one-dark'
import type { ArenaLanguage } from '../../api/types'

interface Props {
  value: string
  language: ArenaLanguage
  onChange: (code: string) => void
  /** Вставка большого фрагмента — сигнал для антисписывания, не запрет. */
  onPaste?: (chars: number) => void
  onSubmitShortcut?: () => void
}

const langExt = (l: ArenaLanguage) => (l === 'python' ? python() : javascript())

/** Редактор кода на CodeMirror 6: подсветка, автодополнение, Tab — отступ, Ctrl+Enter — отправка. */
export default function CodeEditor({ value, language, onChange, onPaste, onSubmitShortcut }: Props) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const lang = useRef(new Compartment())
  const handlers = useRef({ onChange, onPaste, onSubmitShortcut })
  handlers.current = { onChange, onPaste, onSubmitShortcut }

  useEffect(() => {
    if (!host.current) return
    const v = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          keymap.of([
            indentWithTab,
            { key: 'Mod-Enter', run: () => { handlers.current.onSubmitShortcut?.(); return true } },
          ]),
          lang.current.of(langExt(language)),
          oneDark,
          EditorView.lineWrapping,
          EditorView.updateListener.of((u) => {
            if (u.docChanged) handlers.current.onChange(u.state.doc.toString())
          }),
          EditorView.domEventHandlers({
            paste: (e) => {
              const text = e.clipboardData?.getData('text') ?? ''
              handlers.current.onPaste?.(text.length)
              return false
            },
          }),
          EditorView.contentAttributes.of({ 'aria-label': 'Код решения' }),
        ],
      }),
    })
    view.current = v
    return () => v.destroy()
    // редактор создаётся один раз; язык и текст меняются ниже
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    view.current?.dispatch({ effects: lang.current.reconfigure(langExt(language)) })
  }, [language])

  // внешняя смена текста (другая задача, сброс к шаблону)
  useEffect(() => {
    const v = view.current
    if (v && v.state.doc.toString() !== value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } })
    }
  }, [value])

  return <div ref={host} className="code-editor" data-testid="code-editor" />
}
