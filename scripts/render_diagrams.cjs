// Рендер mermaid-схем из docs/guide/*.md в PNG для сборки docx/pdf (scripts/build_docs.py).
// Нужны playwright и mermaid:  npm i --no-save playwright mermaid@11 && node scripts/render_diagrams.cjs
// Схема N из файла 04-arhitektura.md сохраняется как docs/assets/diagrams/04-arhitektura-N.png.
const fs = require('fs')
const path = require('path')
const { chromium } = require('playwright')

const root = path.resolve(__dirname, '..')
const guide = path.join(root, 'docs/guide')
const out = path.join(root, 'docs/assets/diagrams')
const mermaidJs = require.resolve('mermaid/dist/mermaid.min.js')

;(async () => {
  fs.mkdirSync(out, { recursive: true })
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {})
  const page = await browser.newPage({ deviceScaleFactor: 2, viewport: { width: 1200, height: 800 } })
  await page.setContent('<html><body style="margin:0;background:#fff"><div id="d"></div></body></html>')
  await page.addScriptTag({ path: mermaidJs })
  await page.evaluate(() =>
    window.mermaid.initialize({ startOnLoad: false, theme: 'neutral', fontFamily: 'Inter, Arial, sans-serif' }),
  )
  for (const file of fs.readdirSync(guide).filter((f) => f.endsWith('.md')).sort()) {
    const text = fs.readFileSync(path.join(guide, file), 'utf8')
    // для печати широкие схемы «слева направо» разворачиваются сверху вниз, чтобы поместиться на страницу A4
    const blocks = [...text.matchAll(/```mermaid\n([\s\S]*?)```/g)].map((m) => m[1].replace(/^flowchart LR/, 'flowchart TB'))
    for (const [i, src] of blocks.entries()) {
      await page.evaluate(async ([s, id]) => {
        const { svg } = await window.mermaid.render(id, s)
        document.getElementById('d').innerHTML = svg
      }, [src, `m${i}`])
      const name = `${path.basename(file, '.md')}-${i + 1}.png`
      await page.locator('#d svg').screenshot({ path: path.join(out, name) })
      console.log(name)
    }
  }
  await browser.close()
})()
