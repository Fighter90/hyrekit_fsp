import { ArrowDown, ArrowUp, CheckCircle2, RotateCcw } from 'lucide-react'
import type { AttemptResult, Grade } from '../../api/types'
import ScoreRing from '../ui/ScoreRing'
import Bar from '../ui/Bar'
import { Button, LinkButton } from '../ui/Button'
import { CategoryBadge } from '../ui/Badges'
import Reveal from '../ui/Reveal'
import { SUGGESTION_LABEL, gradeLabel } from '../../lib/format'
import { neighbourGrade } from '../../lib/assessment'

interface Props {
  result: AttemptResult
  specTitle: string
  allowedGrades: Grade[]
  onStart: (g: Grade) => void
  onBack: () => void
  starting?: boolean
}

export default function ResultView({ result: r, specTitle, allowedGrades, onStart, onBack, starting }: Props) {
  const target =
    r.suggestion === 'retry_lower' ? neighbourGrade(r.grade_tested, -1) : r.suggestion === 'try_higher' ? neighbourGrade(r.grade_tested, 1) : null
  const canStart = target !== null && allowedGrades.includes(target)
  // Тест не сдан на младшем грейде: сервер оставляет suggestion = keep, но «категория подтверждена» здесь неверно
  const failedKeep = !r.passed && r.suggestion === 'keep'
  const tone = failedKeep ? 'retry_lower' : r.suggestion

  return (
    <div className="result">
      <Reveal className="card card--spin result__hero">
        <ScoreRing value={r.score} size={190} />
        <div className="result__summary">
          <div className="kicker">результат теста · {specTitle} · {gradeLabel(r.grade_tested)}</div>
          <h2 className="result__title display">{r.passed ? 'Грейд подтверждён' : 'Пока не подтверждён'}</h2>
          <p className="muted">
            Верно {r.correct} из {r.total} · оценка способности θ = {r.ability.toFixed(2)}
          </p>
          <div className="result__cat">
            {r.assigned_grade ? (
              <>
                {r.passed && <CheckCircle2 size={18} className="text-success" />}
                <span>{r.passed ? 'Присвоена категория' : 'Остаётся категория прошлого теста'}</span>
                <CategoryBadge title={`${specTitle} · ${gradeLabel(r.assigned_grade)}`} grade={r.assigned_grade} />
              </>
            ) : (
              <span className="muted">Категория не присвоена</span>
            )}
          </div>
          <div className={`suggestion suggestion--${tone}`}>
            {failedKeep ? (
              <RotateCcw size={18} />
            ) : r.suggestion === 'retry_lower' ? (
              <ArrowDown size={18} />
            ) : r.suggestion === 'try_higher' ? (
              <ArrowUp size={18} />
            ) : (
              <CheckCircle2 size={18} />
            )}
            <span>{failedKeep ? 'Верных ответов меньше большинства — разберите темы ниже и попробуйте снова' : SUGGESTION_LABEL[r.suggestion]}</span>
          </div>
          <div className="row wrap gap-sm mt">
            {target && (
              <Button
                variant={r.suggestion === 'try_higher' ? 'primary' : 'secondary'}
                icon={<RotateCcw size={16} />}
                disabled={!canStart}
                loading={starting}
                onClick={() => onStart(target)}
                title={canStart ? undefined : 'Сейчас этот грейд недоступен для сдачи'}
              >
                Сдавать {gradeLabel(target)}
              </Button>
            )}
            <LinkButton to="/app/dashboard" variant="ghost">В кабинет</LinkButton>
            <Button variant="ghost" onClick={onBack}>К тестированию</Button>
          </div>
          {target && !canStart && <p className="muted tiny">Пересдача {gradeLabel(target)} откроется после окончания периода ожидания.</p>}
        </div>
      </Reveal>

      {r.by_topic.length > 0 && (
        <Reveal className="card" delay={120}>
          <div className="card__title">Разбор по темам</div>
          <div className="topic-bars">
            {r.by_topic.map((t) => (
              <Bar
                key={t.topic}
                label={t.topic}
                value={t.correct}
                max={t.total}
                suffix={`${t.correct}/${t.total}`}
                tone={t.total && t.correct / t.total < 0.5 ? 'red' : 'blue'}
              />
            ))}
          </div>
        </Reveal>
      )}
    </div>
  )
}
