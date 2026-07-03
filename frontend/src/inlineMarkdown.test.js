import test from 'node:test'
import assert from 'node:assert/strict'
import { escapeHtml, inlineMarkdown } from './inlineMarkdown.js'

test('inlineMarkdown escapes html before rendering bold markers', () => {
  const html = inlineMarkdown('💡洞察：**重点** <script>alert(1)</script>')

  assert.equal(
    html,
    '💡洞察：<strong>重点</strong> &lt;script&gt;alert(1)&lt;/script&gt;'
  )
})

test('escapeHtml escapes quotes and angle brackets', () => {
  assert.equal(escapeHtml('"x" < y & z'), '&quot;x&quot; &lt; y &amp; z')
})
