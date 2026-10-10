#!/usr/bin/env node
/**
 * Сквозной браузерный тест демо-сценария (FSP-56): всё через интерфейс, как это сделает эксперт.
 *
 *   NODE_PATH=/opt/node-tools/node_modules node scripts/e2e.cjs                       # SPA на :5173
 *   NODE_PATH=$(npm root -g) node scripts/e2e.cjs --base https://hyrekit.ru
 *   node scripts/e2e.cjs --headed --slow 250                                          # смотреть глазами
 *
 * Сценарий 1: кандидат регистрируется → опрос → тест → категория → согласие и ФСП ID;
 * работодатель создаёт потребность → подборка → приглашение; кандидат входит заново и
 * принимает приглашение; работодатель видит контакты в карточке.
 * Сценарий 2: кандидат без ФСП — регистрация, опрос, тест, согласие без ФСП ID.
 *
 * Нужны демо-данные (SEED_DEMO=true): employer@hyrekit.ru / HyreKit2026.
 * Почту подтверждать не нужно: интерфейс не блокирует неподтверждённых, только показывает баннер.
 * Лимиты API: регистрация 3/мин, вход 5/мин с адреса; прогон тратит 2 регистрации и 2 входа,
 * поэтому запускать не чаще раза в минуту.
 *
 * Код выхода 0 — все шаги прошли, 1 — хотя бы один упал (скриншот падения — во временной папке).
 */
'use strict'

const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const crypto = require('node:crypto')

let chromium
try {
  ;({ chromium } = require('playwright'))
} catch {
  console.error('Нет пакета playwright. Укажите NODE_PATH на node_modules с ним, например NODE_PATH=/opt/node-tools/node_modules')
  process.exit(2)
}

const PASSWORD = 'HyreKit2026' // публичный пароль демо-аккаунтов
const EMPLOYER = 'employer@hyrekit.ru'
const FSP_ID = 'FSP-123457' // демо-провайдер ФСП отдаёт по нему историю соревнований
const MAX_ATTEMPTS = 8 // пересдачи Intern, пока тест не подтвердит грейд (см. комментарий у passTest)

function parseArgs(argv) {
  const args = { base: 'http://localhost:5173', headed: false, slow: 0, timeout: 15000 }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--base') args.base = argv[++i]
    else if (a === '--headed') args.headed = true
    else if (a === '--slow') args.slow = Number(argv[++i])
    else if (a === '--timeout') args.timeout = Number(argv[++i])
    else if (a === '-h' || a === '--help') {
      console.log('node scripts/e2e.cjs [--base URL] [--headed] [--slow MS] [--timeout MS]')
      process.exit(0)
    } else {
      console.error(`Неизвестный аргумент: ${a}`)
      process.exit(2)
    }
  }
  args.base = args.base.replace(/\/+$/, '')
  return args
}

const args = parseArgs(process.argv.slice(2))
const shotsDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hyrekit-e2e-'))
const results = []
const pages = new Set() // открытые вкладки — для скриншотов при падении

class StepFailed extends Error {}

/** Шаг сценария: печатает OK/FAIL, при падении снимает скриншоты и останавливает сценарий. */
async function step(name, fn) {
  try {
    const detail = await fn()
    results.push([name, true])
    console.log(`OK   ${name}${detail ? ` — ${detail}` : ''}`)
    return detail
  } catch (e) {
    results.push([name, false])
    const msg = String(e && e.message ? e.message : e).split('\n')[0]
    console.log(`FAIL ${name} — ${msg}`)
    let n = 0
    for (const p of pages) {
      if (p.isClosed()) continue
      const file = path.join(shotsDir, `${String(results.length).padStart(2, '0')}-${++n}.png`)
      await p.screenshot({ path: file, fullPage: true }).catch(() => undefined)
      console.log(`     скриншот: ${file} (${p.url()})`)
    }
    throw new StepFailed(name)
  }
}

function expect(cond, message) {
  if (!cond) throw new Error(message)
}

const uid = () => crypto.randomBytes(4).toString('hex')
const pick = (n) => Math.floor(Math.random() * n)

async function newPage(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: 'ru-RU' })
  ctx.setDefaultTimeout(args.timeout)
  const page = await ctx.newPage()
  pages.add(page)
  return page
}

let employerPage = null

/** Одна сессия демо-работодателя на прогон: экономит лимит входов. */
async function employer(browser) {
  if (employerPage) return employerPage
  const page = await newPage(browser)
  await step('Вход демо-работодателя', () => login(page, EMPLOYER))
  employerPage = page
  return page
}

async function goto(page, route) {
  await page.goto(`${args.base}${route}`)
}

/** Выбор карточки-радиокнопки. */
async function choose(radio) {
  await tick(radio, true)
}

/**
 * Флажок или переключатель: input прячется под оформлением, поэтому клик принудительный.
 * Настройки кандидата сохраняются на сервере и отмечаются после ответа — ждём до таймаута.
 */
async function tick(box, value = true) {
  if ((await box.isChecked()) !== value) await box.click({ force: true })
  const until = Date.now() + args.timeout
  while ((await box.isChecked()) !== value) {
    expect(Date.now() < until, 'отметка не установилась')
    await box.page().waitForTimeout(100)
  }
}

/** Переход по пункту бокового меню кабинета. */
async function nav(page, label, urlPart) {
  await page.getByRole('navigation', { name: 'Кабинет' }).getByRole('link', { name: label, exact: true }).click()
  await page.waitForURL((u) => u.pathname.startsWith(urlPart))
}

async function register(page, fullName, email) {
  await goto(page, '/auth?mode=register')
  await choose(page.getByRole('radio', { name: /^Кандидат/ }))
  await page.getByLabel('Имя и фамилия').fill(fullName)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel(/^Пароль/).fill(PASSWORD)
  await tick(page.getByRole('checkbox', { name: /Принимаю/ }))
  await page.getByRole('button', { name: 'Начать как кандидат' }).click()
  await page.waitForURL('**/app/dashboard')
  await page.getByText(fullName).first().waitFor()
}

async function login(page, email) {
  await goto(page, '/auth')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel(/^Пароль/).fill(PASSWORD)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await page.waitForURL('**/app/dashboard')
}

async function survey(page, { spec, grade, stack }) {
  await nav(page, 'Тестирование', '/app/assessment')
  await page.getByRole('heading', { name: 'Расскажите о себе' }).waitFor()
  await choose(page.getByRole('radio', { name: new RegExp(`^${spec}`) }))
  await page.getByLabel('Отрасль').selectOption('fintech')
  await page.getByLabel('Опыт в специализации, лет').fill('0')
  const tags = page.getByLabel('Стек')
  for (const t of stack) {
    await tags.fill(t)
    await tags.press('Enter')
  }
  await choose(page.getByRole('radio', { name: new RegExp(`^${grade}`) }))
  await page.getByRole('button', { name: 'Сохранить и перейти к тесту' }).click()
  await page.getByRole('button', { name: `Сдавать ${grade}` }).waitFor()
}

/** Один проход теста: любые ответы на все задания в интерфейсе, затем «Завершить». */
async function runTest(page, grade) {
  await page.getByRole('button', { name: `Сдавать ${grade}` }).click()
  const map = page.getByRole('complementary', { name: 'Карта заданий' })
  await map.waitFor()
  const total = await map.getByRole('button', { name: /^Задание \d+/ }).count()
  expect(total > 0, 'тест не выдал заданий')
  for (let i = 1; i <= total; i++) {
    await map.getByRole('button', { name: new RegExp(`^Задание ${i}(,|$)`) }).click()
    await page.getByText(`Задание ${i} / ${total}`).waitFor()
    const item = page.locator('article')
    const number = item.getByLabel('Ваш ответ (число)')
    if (await number.count()) {
      await number.fill(String(pick(10)))
    } else {
      const options = item.getByRole('radio').or(item.getByRole('checkbox'))
      await options.nth(pick(await options.count())).click()
    }
    await map.getByRole('button', { name: new RegExp(`^Задание ${i}, отвечено`) }).waitFor()
  }
  await page.getByRole('button', { name: 'Завершить', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Завершить тест?' })
  await dialog.getByText(`Отвечено ${total} из ${total}`).waitFor()
  await dialog.getByRole('button', { name: 'Завершить и узнать результат' }).click()
  const title = page.getByRole('heading', { name: /Грейд подтверждён|Пока не подтверждён/ })
  await title.waitFor()
  const passed = (await title.textContent()).includes('подтверждён') && !(await title.textContent()).includes('Пока')
  const summary = (await page.getByText(/^Верно \d+ из \d+/).textContent()).trim()
  return { passed, total, summary }
}

/**
 * Тест до подтверждения грейда. Ответы случайные, поэтому Intern подтверждается не всегда
 * (примерно в 6 случаях из 10). Пока грейд не подтверждён, пересдача доступна сразу
 * (assessment.service.eligibility), поэтому пересдаём до MAX_ATTEMPTS раз: вероятность
 * не набрать категорию за все попытки — доли процента.
 */
async function passTest(page, grade) {
  for (let n = 1; n <= MAX_ATTEMPTS; n++) {
    const r = await runTest(page, grade)
    if (r.passed) return { ...r, attempts: n }
    await page.getByRole('button', { name: 'К тестированию' }).click()
  }
  throw new Error(`грейд не подтверждён за ${MAX_ATTEMPTS} попыток`)
}

async function giveConsent(page) {
  await nav(page, 'Настройки', '/app/settings')
  await tick(page.getByRole('checkbox', { name: /Даю согласие на обработку/ }))
  await page.getByText(/Согласие дано \d/).waitFor()
}

async function scenarioWithFsp(browser) {
  const id = uid()
  const name = `Е2Е Кандидат ${id}`
  const email = `e2e-${id}@example.ru`
  const token = `e2e${id}` // уникальная технология: по ней работодатель найдёт именно этого кандидата
  const cand = await newPage(browser)

  console.log('\n— Сценарий 1: кандидат с ФСП и приглашение —')
  await step('Регистрация кандидата через форму', async () => {
    await register(cand, name, email)
    return email
  })
  await step('Почта не блокирует кабинет (баннер подтверждения)', async () => {
    await cand.getByText('Подтвердите почту').waitFor()
  })
  await step('Опрос: Backend, Intern, стек', () => survey(cand, { spec: 'Backend', grade: 'Intern', stack: ['Python', token] }))
  const test = await step('Тест пройден в интерфейсе, категория присвоена', async () => {
    const r = await passTest(cand, 'Intern')
    await cand.getByText('Присвоена категория').waitFor()
    return `${r.total} заданий, ${r.summary.split(' · ')[0]}, попыток ${r.attempts}`
  })
  await step('Категория видна в кабинете', async () => {
    await nav(cand, 'Обзор', '/app/dashboard')
    await cand.getByText('Backend · Intern').first().waitFor()
    await cand.getByText(/Профиль скрыт: нужно согласие/).waitFor()
  })
  await step('Согласие на публикацию', async () => {
    await giveConsent(cand)
    await cand.getByText('Профиль виден работодателям').waitFor()
  })
  await step('Имя открыто работодателям', async () => {
    await tick(cand.getByRole('switch', { name: /Показывать имя/ }))
    await cand.getByText('Настройки приватности сохранены').waitFor()
  })
  await step('ФСП ID привязан, достижения подтянулись', async () => {
    await cand.getByLabel('ФСП ID').fill(FSP_ID)
    await cand.getByRole('button', { name: 'Привязать' }).click()
    const line = (await cand.getByText(`ФСП ID ${FSP_ID} ·`).textContent()).trim()
    expect(Number(line.match(/· (\d+) достижени/)?.[1]) > 0, `нет достижений: ${line}`)
    await cand.getByText('баллы ФСП', { exact: true }).waitFor()
    return line
  })

  // --- Работодатель ---
  const emp = await employer(browser)
  const vacancy = `Стажёр backend (e2e ${id})`
  let profileUrl = ''
  await step('Новая потребность через форму', async () => {
    await nav(emp, 'Потребности', '/app/vacancies')
    await goto(emp, '/app/vacancies/new')
    await emp.getByLabel('Название').fill(vacancy)
    await emp.getByLabel('Специализация').selectOption('backend')
    await emp.getByLabel('Грейд от').selectOption('intern')
    await emp.getByLabel('Грейд до').selectOption('junior')
    await emp.getByLabel(/^От(\s|$)/).fill('90000')
    await emp.getByLabel(/^До(\s|$)/).fill('130000')
    const tags = emp.getByLabel('Стек')
    for (const t of ['Python', token]) {
      await tags.fill(t)
      await tags.press('Enter')
    }
    await emp.getByLabel('Задачи и требования').fill('Сквозной тест: сервисы на Python, код-ревью, тесты.')
    // не публикуем, чтобы прогоны не засоряли ленту вакансий кандидатов на стенде
    await tick(emp.getByRole('switch', { name: /Опубликовать/ }), false)
    await emp.getByRole('button', { name: 'Сохранить и к подборке' }).click()
    await emp.waitForURL(/\/app\/vacancies\/[\w-]+\/matches/)
    await emp.getByRole('heading', { name: vacancy }).waitFor()
  })
  await step('Подборка находит нового кандидата с объяснением', async () => {
    await emp.getByText(/Найдено \d+/).waitFor()
    await emp.getByRole('button', { name: token, exact: true }).click() // фильтр «Обязательный стек»
    const card = emp.getByRole('article').filter({ hasText: name })
    await card.waitFor()
    await card.getByRole('list', { name: 'Почему рекомендован' }).waitFor()
    profileUrl = await card.getByRole('link', { name: 'Профиль' }).getAttribute('href')
    const score = (await card.getByTitle('Итоговый балл совпадения').textContent()).replace(/\D+/g, ' ').trim()
    await card.getByTitle('Достижения в соревнованиях ФСП').waitFor()
    return `балл совпадения ${score}, бейдж ФСП есть`
  })
  await step('Контакты скрыты до ответа кандидата', async () => {
    await goto(emp, profileUrl)
    await emp.getByText('Откроются, когда кандидат примет приглашение').waitFor()
    await emp.getByText(`ФСП ID ${FSP_ID} ·`).waitFor()
    await emp.goBack()
  })
  await step('Приглашение из подборки (InviteModal)', async () => {
    await emp.getByRole('button', { name: token, exact: true }).click()
    const card = emp.getByRole('article').filter({ hasText: name })
    await card.getByRole('button', { name: 'Пригласить' }).click()
    const dialog = emp.getByRole('dialog', { name: 'Пригласить кандидата' })
    expect((await dialog.getByLabel('Позиция').inputValue()) === vacancy, 'позиция не подставилась из потребности')
    expect((await dialog.getByLabel('Зарплата от, ₽').inputValue()) === '90000', 'вилка не подставилась')
    await dialog.getByLabel('Сообщение').fill('Приглашаем на интервью: команда платёжного шлюза, менторство.')
    await dialog.getByLabel('Способ связи').fill('hr@technoplatform.ru')
    await dialog.getByRole('button', { name: 'Отправить приглашение' }).click()
    await dialog.waitFor({ state: 'detached' })
    await card.getByRole('button', { name: 'Приглашён' }).waitFor()
  })

  // --- Кандидат отвечает ---
  await step('Кандидат выходит и входит заново', async () => {
    await cand.getByRole('button', { name: 'Выйти' }).click()
    await cand.waitForURL((u) => u.pathname === '/')
    await login(cand, email)
  })
  await step('Кандидат видит приглашение с вилкой и принимает его', async () => {
    await nav(cand, 'Приглашения', '/app/invitations')
    const inv = cand.getByRole('button', { name: new RegExp(vacancy.replace(/[()]/g, '\\$&')) })
    await inv.getByText('90 000').waitFor()
    await inv.click()
    const dialog = cand.getByRole('dialog', { name: vacancy })
    await dialog.getByRole('button', { name: 'Принять и открыть контакты' }).click()
    await dialog.getByText('Вы приняли приглашение.').waitFor()
    await dialog.getByText('hr@technoplatform.ru').waitFor()
  })
  await step('Работодатель видит контакты в карточке кандидата', async () => {
    await goto(emp, profileUrl)
    const link = emp.getByRole('link', { name: email })
    await link.waitFor()
    await emp.getByRole('heading', { name, level: 1 }).waitFor()
    return email
  })
  return test
}

async function scenarioWithoutFsp(browser) {
  const id = uid()
  const name = `Е2Е БезФСП ${id}`
  const email = `e2e-nofsp-${id}@example.ru`
  const token = `e2e${id}`
  const page = await newPage(browser)

  console.log('\n— Сценарий 2: кандидат без ФСП —')
  await step('Регистрация кандидата без ФСП', () => register(page, name, email))
  await step('Опрос: Frontend, Intern, стек', () => survey(page, { spec: 'Frontend', grade: 'Intern', stack: ['TypeScript', token] }))
  await step('Тест пройден в интерфейсе, категория присвоена', async () => {
    const r = await passTest(page, 'Intern')
    await page.getByText('Присвоена категория').waitFor()
    return `${r.summary.split(' · ')[0]}, попыток ${r.attempts}`
  })
  await step('Согласие без ФСП ID', async () => {
    await giveConsent(page)
    await page.getByText('Профиль виден работодателям').waitFor()
  })
  await step('В настройках нет достижений ФСП, предложено привязать ФСП ID', async () => {
    await page.getByLabel('ФСП ID').waitFor()
    expect((await page.getByText('баллы ФСП', { exact: true }).count()) === 0, 'на странице есть панель достижений')
    await nav(page, 'Обзор', '/app/dashboard')
    await page.getByRole('link', { name: 'привязать ФСП ID' }).waitFor()
  })

  const emp = await employer(browser)
  await step('Банк кандидатов находит кандидата без бейджа ФСП', async () => {
    await nav(emp, 'Банк кандидатов', '/app/candidates')
    await emp.getByLabel('Поиск').fill(token)
    await emp.waitForURL((u) => u.searchParams.get('q') === token)
    await emp.getByText(/^1 кандидат$/).waitFor()
    const card = emp.getByRole('article')
    await card.getByText('Frontend · Intern').waitFor()
    expect((await card.getByTitle('Достижения в соревнованиях ФСП').count()) === 0, 'у кандидата бейдж ФСП')
    await card.getByRole('link', { name: 'Профиль' }).click()
  })
  await step('В карточке кандидата нет достижений ФСП', async () => {
    await emp.waitForURL(/\/app\/candidates\/[\w-]+$/)
    await emp.getByText('Кандидат не привязал ФСП ID или скрыл достижения.').waitFor()
  })
}

/** Стенд жив: SPA отдаётся, API отвечает через тот же адрес. */
async function smoke(browser) {
  const page = await newPage(browser)
  await step('SPA и API отвечают', async () => {
    await goto(page, '/')
    await page.getByRole('link', { name: /Войти|Вход/ }).first().waitFor()
    const health = await page.request.get(`${args.base}/health`)
    expect(health.ok(), `/health → ${health.status()}`)
  })
  pages.delete(page)
  await page.context().close()
}

async function main() {
  console.log(`HyreKit e2e · ${args.base}`)
  const browser = await chromium.launch({ headless: !args.headed, slowMo: args.slow || undefined })
  try {
    for (const scenario of [smoke, scenarioWithFsp, scenarioWithoutFsp]) {
      try {
        await scenario(browser)
      } catch (e) {
        if (!(e instanceof StepFailed)) throw e
        if (scenario === smoke) break // стенд недоступен — дальше идти нет смысла
        console.log('     сценарий остановлен')
      }
    }
  } finally {
    await browser.close()
  }
  const failed = results.filter(([, ok]) => !ok).length
  console.log(`\n${results.length - failed}/${results.length} шагов прошли`)
  if (failed) console.log(`Скриншоты: ${shotsDir}`)
  else fs.rmSync(shotsDir, { recursive: true, force: true })
  return failed ? 1 : 0
}

main().then(
  (code) => process.exit(code),
  (e) => {
    console.error(e)
    process.exit(1)
  },
)
