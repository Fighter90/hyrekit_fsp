#!/usr/bin/env node
/**
 * Сквозной браузерный тест демо-сценария (FSP-56): всё через интерфейс, как это сделает эксперт.
 *
 *   NODE_PATH=/opt/node-tools/node_modules node scripts/e2e.cjs                       # SPA на :5173
 *   NODE_PATH=$(npm root -g) node scripts/e2e.cjs --base https://hyrekit.ru
 *   node scripts/e2e.cjs --headed --slow 250                                          # смотреть глазами
 *
 * Сценарий 1: новый кандидат регистрируется → опрос → тест в интерфейсе → результат
 * согласован с ответами → согласие и ФСП ID с достижениями.
 * Сценарий 2: работодатель создаёт потребность → подборка → приглашает демо-кандидата
 * talent07 → тот входит и принимает приглашение → работодатель видит контакты.
 * Сценарий 3: новый кандидат без ФСП — опрос, тест, согласие без ФСП ID; карточка
 * кандидата без ФСП у работодателя.
 *
 * Новые кандидаты отвечают наугад, поэтому грейд у них, как и положено, обычно не
 * подтверждается: тест проверяет, что результат показан и согласован, а не сам исход.
 * Приглашают поэтому синтетического кандидата из демо-данных — у него есть категория
 * и согласие, а войти за него можно (scripts/smoke.py делает так же).
 *
 * Нужны демо-данные (SEED_DEMO=true): employer@hyrekit.ru и talent07@demo.hyrekit.ru / HyreKit2026.
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
const TALENT = 'talent07@demo.hyrekit.ru' // синтетический кандидат с категорией Backend и согласием
const E2E_MARK = '(e2e ' // метка в названии потребности и приглашения, по ней убираются хвосты прошлых прогонов

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
  return checkResult(page, total)
}

/**
 * Экран результата согласован: «Верно X из N» совпадает с числом заданий и с суммой
 * разбора по темам, вердикт, строка категории и рекомендация не противоречат друг другу.
 * Исход теста не проверяется — при случайных ответах он и должен быть любым.
 */
async function checkResult(page, total) {
  const title = page.getByRole('heading', { name: /Грейд подтверждён|Пока не подтверждён/ })
  await title.waitFor()
  const passed = (await title.textContent()).trim() === 'Грейд подтверждён'
  await page.getByText(/^результат теста ·/).waitFor()
  await page.getByText('баллов', { exact: true }).waitFor() // кольцо с баллом
  const summary = (await page.getByText(/^Верно \d+ из \d+/).textContent()).trim()
  const [, correct, n] = summary.match(/^Верно (\d+) из (\d+)/).map(Number)
  expect(n === total, `«${summary}», а заданий ${total}`)
  await page.getByText('Разбор по темам').waitFor()
  const topics = (await page.getByText(/^\d+\/\d+$/).allTextContents()).map((t) => t.split('/').map(Number))
  const sum = topics.reduce((acc, [c, t]) => [acc[0] + c, acc[1] + t], [0, 0])
  expect(topics.length > 0 && sum[0] === correct && sum[1] === n, `разбор по темам ${sum.join('/')} не сходится с «${summary}»`)
  if (passed) {
    await page.getByText('Присвоена категория').waitFor()
    await page.getByText(/Категория подтверждена|попробуйте грейд выше/).waitFor()
  } else {
    await page.getByText('Категория не присвоена').waitFor()
    await page.getByText('Рекомендуем пересдать на грейд ниже').waitFor()
    await page.getByRole('button', { name: /^Сдавать / }).waitFor()
  }
  return { passed, total, correct, summary: summary.split(' · ')[0] }
}

async function giveConsent(page) {
  await nav(page, 'Настройки', '/app/settings')
  await tick(page.getByRole('checkbox', { name: /Даю согласие на обработку/ }))
  await page.getByText(/Согласие дано \d/).waitFor()
}

/** Токен вошедшего пользователя из localStorage вкладки — для чтения id своего профиля. */
async function profileId(page) {
  const token = await page.evaluate(() => localStorage.getItem('access_token'))
  const r = await page.request.get(`${args.base}/api/v1/candidate/profile`, { headers: { Authorization: `Bearer ${token}` } })
  expect(r.ok(), `/candidate/profile → ${r.status()}`)
  return (await r.json()).id
}

async function freshCandidate(page, { label, name, email, spec, stack }) {
  await step(`Регистрация ${label} через форму`, async () => {
    await register(page, name, email)
    await page.getByText('Подтвердите почту').waitFor() // почта не блокирует кабинет
    return email
  })
  await step(`Опрос: ${spec}, Junior, стек`, () => survey(page, { spec, grade: 'Junior', stack }))
  const r = await step('Тест пройден в интерфейсе, результат согласован', async () => {
    const res = await runTest(page, 'Junior')
    return `${res.summary}, ${res.passed ? 'категория присвоена' : 'грейд не подтверждён, предложен ниже'}`
  })
  return r
}

async function scenarioFsp(browser) {
  const id = uid()
  const cand = await newPage(browser)
  console.log('\n— Сценарий 1: новый кандидат с ФСП —')
  await freshCandidate(cand, {
    label: 'кандидата', name: `Е2Е Кандидат ${id}`, email: `e2e-${id}@example.ru`, spec: 'Backend', stack: ['Python', 'FastAPI'],
  })
  await step('Согласие на публикацию', () => giveConsent(cand))
  await step('ФСП ID привязан, достижения подтянулись', async () => {
    await cand.getByLabel('ФСП ID').fill(FSP_ID)
    await cand.getByRole('button', { name: 'Привязать', exact: true }).click()
    const line = (await cand.getByText(`ФСП ID ${FSP_ID} ·`).textContent()).trim()
    expect(Number(line.match(/· (\d+) достижени/)?.[1]) > 0, `нет достижений: ${line}`)
    await cand.getByText('баллы ФСП', { exact: true }).waitFor()
    return line
  })
  await step('Баллы ФСП в кабинете', async () => {
    await nav(cand, 'Обзор', '/app/dashboard')
    await cand.getByText(/\d+ достижени/).first().waitFor()
  })
  pages.delete(cand)
  await cand.context().close()
}

async function scenarioInvite(browser) {
  const id = uid()
  const vacancy = `Backend-разработчик ${E2E_MARK}${id})`
  const tal = await newPage(browser)
  console.log('\n— Сценарий 2: потребность, подборка, приглашение —')

  let talentId = ''
  let category = ''
  await step('Демо-кандидат talent07 входит, категория и согласие есть', async () => {
    await login(tal, TALENT)
    const badge = await tal.getByText(/Backend · (Intern|Junior|Middle|Senior|Lead)/).first().textContent()
    category = badge.match(/Backend · \w+/)[0]
    await tal.getByText('Профиль виден работодателям').waitFor()
    talentId = await profileId(tal)
    return category
  })
  await step('Хвосты прошлых прогонов отклонены', async () => {
    // упавший прогон мог оставить приглашение без ответа — с ним новое не отправить (409)
    await nav(tal, 'Приглашения', '/app/invitations')
    await tal.getByRole('tab', { name: /^Новые/ }).click()
    let n = 0
    for (;;) {
      const stale = tal.getByRole('button', { name: new RegExp(E2E_MARK.replace(/[()]/g, '\\$&')) })
      await tal.getByRole('tab', { name: /^Новые/ }).waitFor()
      await tal.waitForTimeout(300)
      if (!(await stale.count())) break
      await stale.first().click()
      const dialog = tal.getByRole('dialog')
      await dialog.getByRole('button', { name: 'Отклонить', exact: true }).click()
      await dialog.getByRole('button', { name: 'Отклонить приглашение' }).click()
      await dialog.getByText('Отклонено').waitFor()
      await dialog.getByRole('button', { name: 'Закрыть' }).last().click()
      n++
    }
    return n ? `отклонено ${n}` : 'нет'
  })

  const emp = await employer(browser)
  const grade = category.split(' · ')[1].toLowerCase()
  let card
  await step('Новая потребность через форму', async () => {
    await nav(emp, 'Потребности', '/app/vacancies')
    await goto(emp, '/app/vacancies/new')
    await emp.getByLabel('Название').fill(vacancy)
    await emp.getByLabel('Специализация').selectOption('backend')
    await emp.getByLabel('Грейд от').selectOption(grade)
    await emp.getByLabel('Грейд до').selectOption(grade)
    await emp.getByLabel(/^От(\s|$)/).fill('250000')
    await emp.getByLabel(/^До(\s|$)/).fill('320000')
    const tags = emp.getByLabel('Стек')
    for (const t of ['Python', 'PostgreSQL']) {
      await tags.fill(t)
      await tags.press('Enter')
    }
    await emp.getByLabel('Задачи и требования').fill('Сквозной тест: сервисы на Python, код-ревью, тесты.')
    // не публикуем, чтобы прогоны не засоряли ленту вакансий кандидатов на стенде
    await tick(emp.getByRole('switch', { name: /Опубликовать/ }), false)
    await emp.getByRole('button', { name: 'Сохранить и к подборке' }).click()
    await emp.waitForURL(/\/app\/vacancies\/[\w-]+\/matches/)
    await emp.getByRole('heading', { name: vacancy }).waitFor()
    return `Backend, ${category.split(' · ')[1]}`
  })
  await step('Подборка: talent07 с баллом и причинами', async () => {
    const summary = (await emp.getByText(/^Найдено \d+/).textContent()).trim()
    card = emp.getByRole('article').filter({ has: emp.locator(`a[href="/app/candidates/${talentId}"]`) }).first()
    await card.waitFor()
    await card.getByRole('list', { name: 'Почему рекомендован' }).waitFor()
    const score = (await card.getByTitle('Итоговый балл совпадения').textContent()).replace(/\D+/g, ' ').trim()
    return `${summary}; балл talent07 ${score}`
  })
  await step('Приглашение из подборки (InviteModal)', async () => {
    // после прошлых прогонов приглашение могло быть принято — пригласить снова можно
    await card.getByRole('button', { name: 'Пригласить' }).click()
    const dialog = emp.getByRole('dialog', { name: 'Пригласить кандидата' })
    expect((await dialog.getByLabel('Позиция').inputValue()) === vacancy, 'позиция не подставилась из потребности')
    expect((await dialog.getByLabel('Зарплата от, ₽').inputValue()) === '250000', 'вилка не подставилась')
    await dialog.getByLabel('Сообщение').fill('Приглашаем на интервью: команда платёжного шлюза, менторство.')
    await dialog.getByLabel('Способ связи').fill('hr@technoplatform.ru')
    await dialog.getByRole('button', { name: 'Отправить приглашение' }).click()
    await dialog.waitFor({ state: 'detached' })
    await card.getByRole('button', { name: 'Приглашён' }).waitFor()
  })
  await step('Пока нет ответа, повторно пригласить нельзя', async () => {
    await goto(emp, `/app/candidates/${talentId}`)
    await emp.getByRole('button', { name: 'Приглашение отправлено' }).waitFor()
    expect(await emp.getByRole('button', { name: 'Приглашение отправлено' }).isDisabled(), 'кнопка активна')
  })
  await step('Кандидат видит приглашение с вилкой и принимает его', async () => {
    await goto(tal, '/app/invitations')
    const inv = tal.getByRole('button', { name: new RegExp(vacancy.replace(/[()]/g, '\\$&')) })
    await inv.getByText('250 000').waitFor()
    await inv.click()
    const dialog = tal.getByRole('dialog', { name: vacancy })
    await dialog.getByRole('button', { name: 'Принять и открыть контакты' }).click()
    await dialog.getByText('Вы приняли приглашение.').waitFor()
    await dialog.getByText('hr@technoplatform.ru').waitFor()
  })
  await step('Работодатель видит контакты в карточке кандидата', async () => {
    await emp.reload()
    await emp.getByRole('link', { name: TALENT }).waitFor()
    await emp.getByRole('button', { name: 'Пригласить' }).waitFor() // принятое не мешает новому приглашению
    return TALENT
  })
  pages.delete(tal)
  await tal.context().close()
}

async function scenarioNoFsp(browser) {
  const id = uid()
  const token = `e2e${id}` // уникальная технология: по ней кандидата можно найти в банке
  const page = await newPage(browser)
  console.log('\n— Сценарий 3: кандидат без ФСП —')
  const res = await freshCandidate(page, {
    label: 'кандидата без ФСП', name: `Е2Е БезФСП ${id}`, email: `e2e-nofsp-${id}@example.ru`, spec: 'Frontend', stack: ['TypeScript', token],
  })
  await step('Согласие без ФСП ID', () => giveConsent(page))
  await step('В настройках нет достижений ФСП, предложено привязать ФСП ID', async () => {
    await page.getByLabel('ФСП ID').waitFor()
    expect((await page.getByText('баллы ФСП', { exact: true }).count()) === 0, 'на странице есть панель достижений')
    await nav(page, 'Обзор', '/app/dashboard')
    await page.getByRole('link', { name: 'привязать ФСП ID' }).waitFor()
  })

  // Без категории новый кандидат работодателю не виден (так и должно быть), поэтому
  // карточку «без ФСП» тогда смотрим у демо-кандидата Frontend без достижений из банка.
  const fresh = res.includes('категория присвоена')
  const freshId = fresh ? await profileId(page) : null
  const emp = await employer(browser)
  await step('Банк кандидатов: кандидат без бейджа ФСП', async () => {
    await nav(emp, 'Банк кандидатов', '/app/candidates')
    await emp.getByLabel('Специализация').selectOption('frontend')
    await emp.waitForURL((u) => u.searchParams.get('specialization') === 'frontend')
    if (fresh) {
      await emp.getByLabel('Поиск').fill(token)
      await emp.waitForURL((u) => u.searchParams.get('q') === token)
    }
    await emp.getByText(/^\d+ кандидат/).waitFor()
    let card = emp.getByRole('article').filter({ hasNot: emp.getByTitle('Достижения в соревнованиях ФСП') })
    if (fresh) card = card.filter({ has: emp.locator(`a[href="/app/candidates/${freshId}"]`) })
    card = card.first()
    await card.waitFor()
    const who = (await card.getByRole('link').first().textContent()).trim()
    await card.getByRole('link', { name: 'Профиль' }).click()
    return fresh ? `новый кандидат ${who}` : `демо-кандидат ${who}`
  })
  await step('В карточке кандидата нет достижений ФСП', async () => {
    await emp.waitForURL(/\/app\/candidates\/[\w-]+$/)
    await emp.getByText(/Кандидат не привязал ФСП ID|соревновательной истории пока нет/).waitFor()
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
    for (const scenario of [smoke, scenarioFsp, scenarioInvite, scenarioNoFsp]) {
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
