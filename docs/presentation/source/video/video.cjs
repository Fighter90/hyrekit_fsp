// Демо-видео HyreKit: запись сквозного сценария в браузере с титрами.
// node video.cjs <base> <outdir> <db>
// <db> — SQLite стенда (ответы теста и эталоны Arena берутся из него, чтобы показать верное решение).
const { chromium } = require('playwright')
const { execFileSync } = require('child_process')
const [base, out, db] = process.argv.slice(2)
const S = __dirname
const SRC = require('path').resolve(S, '../../../../src')
const CHROME = process.env.CHROME_PATH || undefined
const W = 1280, H = 720
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const CAPTION_CSS = `
#demo-cap{position:fixed;left:24px;right:24px;bottom:22px;z-index:2147483647;pointer-events:none;
 background:linear-gradient(90deg,rgba(82,9,120,.94),rgba(255,0,83,.9));color:#fff;border-radius:14px;
 padding:12px 20px;font:500 19px/1.35 Montserrat,Inter,system-ui,sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.35)}
#demo-cap b{display:block;font-weight:700;font-size:13px;letter-spacing:.08em;text-transform:uppercase;opacity:.85;margin-bottom:2px}`

async function cap(p, step, text) {
  await p.evaluate(([css, step, text]) => {
    let s = document.getElementById('demo-cap-style')
    if (!s) { s = document.createElement('style'); s.id = 'demo-cap-style'; s.textContent = css; document.head.appendChild(s) }
    let d = document.getElementById('demo-cap')
    if (!d) { d = document.createElement('div'); d.id = 'demo-cap'; document.body.appendChild(d) }
    d.innerHTML = '<b>' + step + '</b>' + text
  }, [CAPTION_CSS, step, text])
}

async function card(p, title, sub, ms) {
  await p.setContent(`<html><body style="margin:0;height:100vh;display:flex;flex-direction:column;justify-content:center;
    padding:0 90px;background:linear-gradient(135deg,#310F53,#520978 55%,#FF0053);color:#fff;font-family:Montserrat,sans-serif">
    <div style="font-size:16px;letter-spacing:.2em;opacity:.8">ХАКАТОН ФСП 2026 · КОМАНДА 1</div>
    <div style="font-size:72px;font-weight:800;margin:12px 0">${title}</div>
    <div style="font-size:26px;line-height:1.4;max-width:980px">${sub}</div></body></html>`)
  await sleep(ms)
}

async function slowScroll(p, dy, steps = 12) {
  for (let i = 0; i < steps; i++) { await p.mouse.wheel(0, dy / steps); await sleep(120) }
}

;(async () => {
  const b = await chromium.launch({ executablePath: CHROME })
  const ctx = await b.newContext({ timezoneId: 'Europe/Moscow', viewport: { width: W, height: H }, recordVideo: { dir: out, size: { width: W, height: H } } })
  const p = await ctx.newPage()

  await card(p, 'HyreKit', 'Не ищи работу. Покажи уровень.<br>Кандидат подтверждает грейд тестом, работодатель получает подборку с объяснимым баллом.', 5000)

  // 1. Лендинг
  await p.goto(base + '/', { waitUntil: 'domcontentloaded' }); await sleep(1800)
  await cap(p, '1 · Лендинг', 'Два входа: кандидат и работодатель. Жюри может начать с экспресс-теста без регистрации.')
  await sleep(3500); await slowScroll(p, 900); await sleep(1500); await slowScroll(p, -900, 6)

  // 2. Экспресс-тест
  await p.goto(base + '/express', { waitUntil: 'domcontentloaded' }); await sleep(1800)
  await cap(p, '2 · Тестирование', 'Экспресс-тест: 5 заданий за 5 минут. Выбираем специализацию и грейд, который хотим подтвердить.')
  await sleep(2500)
  await p.selectOption('#express-grade', 'middle').catch(() => {})
  await sleep(1200)
  await p.getByRole('checkbox').first().check(); await sleep(800)
  await p.getByRole('button', { name: /Начать экспресс-тест/ }).click()
  await p.waitForSelector('text=Задание 1 / 5', { timeout: 20000 })
  const answers = JSON.parse(execFileSync('python3', [S + '/answers.py', db], { env: { ...process.env, PYTHONPATH: SRC } }).toString())
  const notes = [
    'Условие собрано генератором из случайных данных: у соседа задание другое, выученный ответ не поможет.',
    'Ответ вычисляет код задания, а не список правильных ответов. Ответы сохраняются, таймер на экране.',
    'Темы и уровни заданий одинаковы для всех, кто проверяет этот грейд.',
    'Концептуальных заданий в попытке не больше одного: их легче выучить.',
    'Грейд подтверждается только большинством верных ответов: 3 из 5 в экспресс-тесте.',
  ]
  for (let i = 0; i < 5; i++) {
    await cap(p, `2 · Задание ${i + 1} из 5`, notes[i])
    const body = await p.locator('main').innerText()
    const a = answers.find((x) => body.includes(x.stem.slice(0, 40))) || answers[i]
    await sleep(2500)
    if (a.kind === 'number') await p.locator('input[id^=num-]').fill(String(a.answer))
    else for (const k of [].concat(a.answer)) { await p.locator('.option').nth(k).click(); await sleep(400) }
    await sleep(1500)
    if (i < 4) await p.getByRole('button', { name: 'Далее' }).click()
  }
  await p.getByRole('button', { name: /^Завершить$/ }).click(); await sleep(800)
  await p.getByRole('button', { name: 'Завершить и узнать результат' }).click()
  await p.waitForSelector('.result', { timeout: 20000 })
  await cap(p, '3 · Автопроверка', 'Оценка способности θ по модели Раша, балл и разбор по темам. Грейд подтверждён, категория присвоена.')
  await sleep(4500); await slowScroll(p, 500); await sleep(3000)

  // 3. Code Arena
  const token = await p.evaluate(() => localStorage.getItem('access_token'))
  const api = async (path) => (await p.request.get(base + '/api/v1' + path, { headers: { Authorization: 'Bearer ' + token } })).json()
  const profile = await api('/candidate/profile')
  await p.goto(base + '/app/arena', { waitUntil: 'domcontentloaded' }); await sleep(1800)
  await cap(p, '4 · Code Arena', 'Решение задач по коду в браузере: открытый раунд, рейтинг Glicko-2, раунды компаний.')
  await sleep(3500)
  const href = await p.locator('a[href^="/app/arena/"]').first().getAttribute('href')
  const roundId = href.split('/').pop()
  await p.goto(base + href, { waitUntil: 'domcontentloaded' }); await sleep(1800)
  const join = p.getByRole('button', { name: 'Участвовать' })
  if (await join.count()) { await cap(p, '4 · Code Arena', 'Участник получает свой вариант задач: числа в условии и тесты у каждого свои.'); await sleep(2500); await join.click() }
  await p.waitForSelector('.code-editor .cm-content', { timeout: 15000 })
  const refs = JSON.parse(execFileSync('python3', [S + '/refs.py', roundId, profile.id], { env: { ...process.env, PYTHONPATH: SRC } }).toString())
  const setCode = async (code) => {
    await p.click('.code-editor .cm-content'); await p.keyboard.press('Control+A'); await p.keyboard.press('Delete')
    await sleep(400); await p.keyboard.insertText(code); await sleep(1200)
  }
  const tab = async (i) => { await p.locator('[role=tab]').nth(i).click(); await sleep(600) }
  const submit = async () => {
    await p.getByRole('button', { name: /Отправить/ }).click()
    await p.waitForSelector('.arena-result', { timeout: 60000 })
    await p.waitForFunction(() => !document.querySelector('.arena-result')?.innerText.includes('Проверяется'), null, { timeout: 90000 })
  }
  await tab(0)
  await cap(p, '5 · Решение задач', 'Пишем решение в редакторе. «Запустить на примерах» не засчитывается в рейтинг.')
  await setCode(refs['sum-multiples'])
  await sleep(800)
  await p.getByRole('button', { name: /Запустить/ }).click(); await sleep(4500)
  await cap(p, '6 · Автопроверка кода', 'Отправка проверяется на скрытых тестах в песочнице без сети: вердикт и время по каждому тесту.')
  await submit(); await sleep(1000)
  await p.locator('.arena-result').scrollIntoViewIfNeeded(); await sleep(4000)
  await p.evaluate(() => window.scrollTo(0, 0)); await tab(1)
  await cap(p, '7 · Обратная связь', 'Неверное решение: модель (GigaChat, резерв YandexGPT) объясняет, в чём ошибка, не выдавая готовый код.')
  await setCode("import sys\nfor line in sys.stdin.read().split()[1:]:\n    print('YES')")
  await submit(); await sleep(800)
  await p.locator('.arena-result').scrollIntoViewIfNeeded(); await p.evaluate(() => window.scrollBy(0, 160)); await sleep(7000)
  await p.locator('.arena-board').scrollIntoViewIfNeeded()
  await cap(p, '8 · Таблица раунда', 'Таблица обновляется в реальном времени. Рейтинг Arena входит в балл подборки работодателя.')
  await sleep(5000)

  // 4. Работодатель
  const v1 = await p.video().path(); await ctx.close()
  const ctx2 = await b.newContext({ timezoneId: 'Europe/Moscow', viewport: { width: W, height: H }, recordVideo: { dir: out + '/emp', size: { width: W, height: H } } })
  const e = await ctx2.newPage()
  await e.goto(base + '/auth', { waitUntil: 'domcontentloaded' }); await sleep(1800)
  // ФСП ID — до входа работодателя
  const fsp = e.getByRole('button', { name: /ФСП ID/ }).first()
  if (await fsp.count()) {
    await cap(e, '9 · ФСП ID', 'Вход через ФСП ID по OpenID Connect с PKCE: профиль участника помечается как подтверждённый.')
    await sleep(2500); await fsp.click(); await sleep(3500)
    await cap(e, '9 · ФСП ID', 'Сейчас работает тестовый провайдер; Keycloak ФСП подключается переменными окружения.')
    await sleep(4000)
  }
  await e.goto(base + '/auth', { waitUntil: 'domcontentloaded' }); await sleep(1800)
  await cap(e, '10 · Работодатель', 'Вход работодателя: employer@hyrekit.ru. Работодатель описывает потребность по форме из ТЗ.')
  await e.fill('input[type=email]', 'employer@hyrekit.ru'); await sleep(400)
  await e.fill('input[type=password]', 'HyreKit2026'); await sleep(800)
  await e.locator('form button[type=submit]').first().click(); await e.waitForURL('**/app/dashboard'); await sleep(2500)
  await cap(e, '10 · Работодатель', 'Кабинет: потребности, подборки, приглашения, короткие задания и Arena.')
  await sleep(3000)
  const etok = await e.evaluate(() => localStorage.getItem('access_token'))
  const vac = await (await e.request.get(base + '/api/v1/employer/vacancies', { headers: { Authorization: 'Bearer ' + etok } })).json()
  const vid = (vac.items || vac)[0].id
  await e.goto(base + `/app/vacancies/${vid}/matches`, { waitUntil: 'domcontentloaded' }); await sleep(1800); await sleep(1500)
  await cap(e, '11 · Подборка', 'Кандидаты по убыванию балла 0–100. У каждого видно, за что балл и какого стека не хватает.')
  await sleep(4500); await slowScroll(e, 600); await sleep(3500)
  const inviteBtn = e.getByRole('button', { name: /Пригласить/ }).first()
  if (await inviteBtn.count()) {
    await inviteBtn.click(); await sleep(1200)
    await cap(e, '12 · Приглашение', 'Приглашение всегда с вилкой зарплаты. Контакты кандидата открываются только после его согласия.')
    await sleep(5000); await e.keyboard.press('Escape'); await sleep(800)
  }
  await e.goto(base + '/app/arena', { waitUntil: 'domcontentloaded' }); await sleep(1800)
  await cap(e, '13 · Витрина Arena', 'Компания сама забирает лучших: витрина по рейтингу Arena и «Раунд компании» на своих задачах.')
  await sleep(5000)

  await card(e, 'hyrekit.ru', 'Экспресс-тест без регистрации — hyrekit.ru/express<br>Код и документация — github.com/Fighter90/hyrekit_fsp', 5000)

  const v2 = await e.video().path()
  await ctx2.close(); await b.close()
  console.log(JSON.stringify({ v1, v2 }))
})().catch((err) => { console.error('FAIL', err); process.exit(1) })
