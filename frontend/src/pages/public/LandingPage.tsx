import { useState, type PointerEvent, type ReactNode } from 'react'
import {
  ArrowRight, UserRound, Building2, ClipboardCheck, BadgeCheck, Mail, Search, Wallet, Sparkles,
  ShieldCheck, Shuffle, Gauge, Eye, Trophy, Plus,
} from 'lucide-react'
import { LinkButton } from '../../components/ui/Button'
import GlyphStrip from '../../components/ui/GlyphStrip'
import Typing from '../../components/ui/Typing'
import Reveal from '../../components/ui/Reveal'
import Counter from '../../components/ui/Counter'
import Tabs from '../../components/ui/Tabs'
import { useAuth } from '../../contexts/AuthContext'
import { useCatalog } from '../../contexts/CatalogContext'

/** Карточка с подсветкой, следующей за курсором. */
function SpotCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`)
    e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`)
  }
  return (
    <div className={`card card--glow card--hover spot ${className}`} onPointerMove={onMove}>
      {children}
    </div>
  )
}

const CANDIDATE_STEPS = [
  { icon: UserRound, title: 'Профиль', text: 'Загрузите резюме PDF/DOCX — поля анкеты заполнятся автоматически. Поправьте и дополните стек.' },
  { icon: ClipboardCheck, title: 'Опрос и тест', text: 'Выберите специализацию и грейд, пройдите тест из 10 заданий. Варианты у всех разные, сложность одинаковая.' },
  { icon: BadgeCheck, title: 'Категория', text: 'По результату вы получаете категорию «специализация · грейд» и рейтинг внутри неё.' },
  { icon: Mail, title: 'Приглашения', text: 'Работодатели сами пишут вам — с названием позиции и зарплатной вилкой. Вы принимаете или отклоняете.' },
]

const EMPLOYER_STEPS = [
  { icon: Building2, title: 'Компания', text: 'Заполните профиль компании — его увидят кандидаты в приглашении.' },
  { icon: Search, title: 'Потребность', text: 'Опишите вакансию: специализация, диапазон грейдов, стек и обязательная вилка зарплаты.' },
  { icon: Sparkles, title: 'Подборка', text: 'Система ранжирует кандидатов подходящих категорий и объясняет каждую рекомендацию.' },
  { icon: Wallet, title: 'Приглашение', text: 'Отправьте приглашение с зарплатой. Контакты откроются, когда кандидат его примет.' },
]

const FAQ = [
  {
    q: 'Что такое «обратный найм»?',
    a: 'Кандидат не рассылает резюме. Он один раз подтверждает уровень тестом и получает категорию. Дальше работодатели сами находят его в банке кандидатов и присылают приглашения с конкретной зарплатой.',
  },
  {
    q: 'Как формируется категория?',
    a: 'Категория — это пара «специализация · грейд», например Backend · Middle. Вы заявляете грейд в опросе, тест его подтверждает или предлагает пересдать на соседний. Рейтинг внутри категории учитывает результат теста и достижения ФСП.',
  },
  {
    q: 'Можно ли списать ответы?',
    a: 'Задания параметрические: у каждого кандидата свои числа, данные и порядок вариантов, а правильный ответ вычисляется. Сложность заданий сопоставима, поэтому результаты честно сравнимы.',
  },
  {
    q: 'Как часто можно менять грейд?',
    a: 'Повысить или понизить подтверждённый грейд можно не чаще одного раза в 90 дней — так категория остаётся надёжным сигналом для работодателей.',
  },
  {
    q: 'Зачем привязывать ФСП ID?',
    a: 'Участие и призовые места в соревнованиях Федерации спортивного программирования подтягиваются автоматически и повышают рейтинг. Если истории нет — ничего страшного, рейтинг считается по тесту.',
  },
  {
    q: 'Кто видит мои контакты?',
    a: 'До принятия приглашения работодатель видит только категорию, стек и результаты. Имя, город и зарплатные ожидания можно скрыть в настройках приватности. Профиль виден только после согласия на обработку данных (152-ФЗ).',
  },
  {
    q: 'Сколько это стоит?',
    a: 'Для кандидатов платформа бесплатна.',
  },
]

const GRADES = [
  { g: 'Intern', w: 22, y: 'без опыта' },
  { g: 'Junior', w: 40, y: 'до 1–2 лет' },
  { g: 'Middle', w: 62, y: '2–4 года' },
  { g: 'Senior', w: 82, y: '4–7 лет' },
  { g: 'Lead', w: 100, y: '7+ лет' },
]

export default function LandingPage() {
  const { isAuthenticated } = useAuth()
  const { catalog } = useCatalog()
  const specs = catalog?.specializations ?? []
  const cooldown = catalog?.grade_change_cooldown_days ?? 90
  const [side, setSide] = useState<'candidate' | 'employer'>('candidate')
  const steps = side === 'candidate' ? CANDIDATE_STEPS : EMPLOYER_STEPS
  const candLink = isAuthenticated ? '/app' : '/auth?mode=register&role=candidate'
  const empLink = isAuthenticated ? '/app' : '/auth?mode=register&role=employer'

  return (
    <div className="landing">
      {/* ============ HERO ============ */}
      <section className="hero">
        <div className="hero__orb hero__orb--blue" aria-hidden />
        <div className="hero__orb hero__orb--red" aria-hidden />
        <div className="container hero__inner">
          <div className="hero__copy">
            <div className="hero__kicker">
              <span className="pulse-dot" /> обратный найм · при поддержке ФСП
            </div>
            <h1 className="hero__title">
              <span className="display">Не ищи работу.</span>
              <span className="display hero__title-accent">Покажи уровень.</span>
            </h1>
            <p className="hero__lead">
              HyreKit подбирает{' '}
              <Typing words={['backend-разработчиков', 'frontend-инженеров', 'data-аналитиков', 'DevOps-инженеров', 'QA-инженеров', 'специалистов по ИБ']} />
              <br />
              Кандидат проходит опрос и тест и получает категорию. Работодатели приходят сами — с приглашением и зарплатой.
            </p>
            <div className="hero__cta">
              <LinkButton to={candLink} size="lg" iconRight={<ArrowRight size={18} />}>
                Я кандидат
              </LinkButton>
              <LinkButton to={empLink} size="lg" variant="ghost" icon={<Building2 size={18} />}>
                Я работодатель
              </LinkButton>
            </div>
            <ul className="hero__bullets">
              <li><ShieldCheck size={16} /> Контакты скрыты до согласия</li>
              <li><Wallet size={16} /> Зарплата — в каждом приглашении</li>
            </ul>
          </div>

          <div className="hero__visual" aria-hidden>
            <div className="terminal">
              <div className="terminal__bar">
                <span /><span /><span />
                <em>hyrekit — assessment</em>
              </div>
              <pre className="terminal__body">
                <code>
                  <span className="t-line" style={{ animationDelay: '0.2s' }}><b className="t-prompt">$</b> hyrekit assess --spec backend</span>
                  <span className="t-line" style={{ animationDelay: '0.8s' }}><i>›</i> опрос <u>..........</u> <b className="t-ok">ok</b></span>
                  <span className="t-line" style={{ animationDelay: '1.3s' }}><i>›</i> тест 9/10 <u>.....</u> <b className="t-num">84</b> балла</span>
                  <span className="t-line" style={{ animationDelay: '1.8s' }}><i>›</i> категория <u>......</u> <b className="t-cat">[Backend · Middle]</b></span>
                  <span className="t-line" style={{ animationDelay: '2.3s' }}><i>›</i> рейтинг ФСП <u>....</u> <b className="t-red">+12</b></span>
                  <span className="t-line" style={{ animationDelay: '2.8s' }}><i>›</i> приглашения <u>....</u> <b className="t-ok">3 новых</b><span className="t-caret">_</span></span>
                </code>
              </pre>
            </div>
            <div className="invite-float">
              <div className="invite-float__head">
                <Mail size={16} /> Приглашение
                <span className="status status--sent">Новое</span>
              </div>
              <strong>Python backend-разработчик</strong>
              <div className="invite-float__salary">220 000 – 280 000 ₽</div>
              <small>Пример карточки приглашения</small>
            </div>
          </div>
        </div>
        <div className="hero__strips">
          <GlyphStrip speed={50} />
          <GlyphStrip speed={65} reverse className="hero__strip-2" />
        </div>
      </section>

      {/* ============ ЦИФРЫ МЕХАНИКИ ============ */}
      <section className="container stats-band">
        {[
          { v: specs.length || 6, s: '', l: specs.length ? `направлений: ${specs.map((x) => x.title).join(', ')}` : 'направлений: от backend до информационной безопасности' },
          { v: 5, s: '', l: 'грейдов: от Intern до Lead' },
          { v: cooldown, s: ' дн', l: 'между сменами грейда — категория остаётся честной' },
          { v: 0, s: ' ₽', l: 'для кандидатов' },
        ].map((x, i) => (
          <Reveal key={x.l} delay={i * 80} className="stats-band__item">
            <div className="stats-band__value display">
              <Counter value={x.v} suffix={x.s} />
            </div>
            <div className="stats-band__label">{x.l}</div>
          </Reveal>
        ))}
      </section>

      {/* ============ КАК ЭТО РАБОТАЕТ ============ */}
      <section id="how" className="section container">
        <Reveal className="section__head">
          <div className="kicker">// как это работает</div>
          <h2 className="section__title display">Найм наоборот</h2>
          <p className="section__lead">
            Не кандидат стучится к работодателю, а работодатель выбирает из проверенных кандидатов и делает предложение первым.
          </p>
          <Tabs
            tabs={[
              { key: 'candidate', label: 'Для кандидата' },
              { key: 'employer', label: 'Для работодателя' },
            ]}
            value={side}
            onChange={setSide}
          />
        </Reveal>
        <div className="steps" key={side}>
          {steps.map((s, i) => (
            <Reveal key={s.title} delay={i * 90}>
              <SpotCard className="step">
                <div className="step__num">0{i + 1}</div>
                <div className="step__icon"><s.icon size={22} /></div>
                <h3 className="step__title">{s.title}</h3>
                <p className="step__text">{s.text}</p>
              </SpotCard>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ============ ТЕСТИРОВАНИЕ ============ */}
      <section id="testing" className="section container">
        <div className="split">
          <Reveal className="split__copy">
            <div className="kicker">// механика тестирования</div>
            <h2 className="section__title display">Грейд подтверждается, а не заявляется</h2>
            <p className="section__lead">
              Короткий опрос определяет специализацию, отрасль и стек. Затем — тест под заявленный грейд: задания по темам
              специализации, от лёгких к экспертным.
            </p>
            <div className="features">
              {[
                { icon: Shuffle, t: 'Параметрические задания', d: 'Свои числа и порядок вариантов у каждого — слитые ответы бесполезны.' },
                { icon: Gauge, t: 'Оценка способности', d: 'Учитывается сложность заданий, а не просто процент верных.' },
                { icon: Eye, t: 'Прозрачный результат', d: 'Разбор по темам и рекомендация: остаться, пересдать ниже или попробовать выше.' },
              ].map((f) => (
                <div className="feature" key={f.t}>
                  <span className="feature__icon"><f.icon size={18} /></span>
                  <div>
                    <strong>{f.t}</strong>
                    <p>{f.d}</p>
                  </div>
                </div>
              ))}
            </div>
          </Reveal>
          <Reveal delay={150} className="split__visual">
            <div className="card card--spin ladder">
              <div className="ladder__head">
                <span className="kicker">категория</span>
                <span className="cat-badge"><span className="cat-badge__bracket">[</span>Backend · Middle<span className="cat-badge__bracket">]</span></span>
              </div>
              {GRADES.map((g, i) => (
                <div key={g.g} className={`ladder__row ${g.g === 'Middle' ? 'is-hit' : ''}`}>
                  <span className="ladder__g">{g.g}</span>
                  <span className="ladder__track"><span className="ladder__fill" style={{ width: `${g.w}%`, transitionDelay: `${i * 120}ms` }} /></span>
                  <span className="ladder__y">{g.y}</span>
                </div>
              ))}
              <p className="ladder__note">Иллюстрация: заявлен Middle, тест подтвердил — профиль виден работодателям в категории.</p>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ============ ФСП ============ */}
      <section id="fsp" className="section container">
        <Reveal>
          <div className="fsp-block card">
            <div className="fsp-block__star" aria-hidden>
              <img src="/brand/fsp-star-dark.svg" alt="" />
            </div>
            <div className="fsp-block__copy">
              <div className="kicker">// буст за достижения ФСП</div>
              <h2 className="section__title display">Соревнования — тоже опыт</h2>
              <p className="section__lead">
                Привяжите ФСП ID — участие и призовые места в соревнованиях Федерации спортивного программирования
                подтянутся автоматически, повысят рейтинг и появятся в карточке для работодателя.
              </p>
              <ul className="fsp-block__list">
                <li><Trophy size={16} /> Призовые места весят больше участия</li>
                <li><BadgeCheck size={16} /> Учитывается связь дисциплины со специализацией</li>
                <li><ShieldCheck size={16} /> Показ достижений можно выключить в настройках</li>
              </ul>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ============ CTA ============ */}
      <section className="section container">
        <Reveal>
          <div className="cta-band card card--spin">
            <GlyphStrip speed={35} className="cta-band__strip" />
            <h2 className="display cta-band__title">Готовы к найму наоборот?</h2>
            <p className="muted">Регистрация занимает минуту. Роль выбирается при регистрации.</p>
            <div className="hero__cta center">
              <LinkButton to={candLink} size="lg" iconRight={<ArrowRight size={18} />}>Пройти тест</LinkButton>
              <LinkButton to={empLink} size="lg" variant="accent" icon={<Building2 size={18} />}>Найти специалистов</LinkButton>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ============ FAQ ============ */}
      <section id="faq" className="section container faq">
        <Reveal className="section__head">
          <div className="kicker">// faq</div>
          <h2 className="section__title display">Вопросы и ответы</h2>
        </Reveal>
        <div className="faq__list">
          {FAQ.map((f, i) => (
            <Reveal key={f.q} delay={i * 50}>
              <details className="faq__item">
                <summary>
                  <span>{f.q}</span>
                  <Plus size={18} className="faq__icon" aria-hidden />
                </summary>
                <p>{f.a}</p>
              </details>
            </Reveal>
          ))}
        </div>
      </section>
    </div>
  )
}
