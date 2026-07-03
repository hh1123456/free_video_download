import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PARSE_PROGRESS_STEPS,
  getParseProgressStep,
  nextParseProgressPercent,
} from './parseProgress.js'

test('parse progress exposes the expected staged labels', () => {
  assert.deepEqual(PARSE_PROGRESS_STEPS.map((step) => step.label), [
    '校验链接',
    '连接解析服务',
    '识别平台并获取视频信息',
    '整理清晰度 / 字幕 / 封面',
    '生成结果卡片',
  ])
})

test('getParseProgressStep maps percent to the current stage', () => {
  assert.equal(getParseProgressStep(0).key, 'validate')
  assert.equal(getParseProgressStep(50).key, 'fetch')
  assert.equal(getParseProgressStep(80).key, 'organize')
  assert.equal(getParseProgressStep(100).key, 'render')
})

test('nextParseProgressPercent advances but caps while request is pending', () => {
  assert.equal(nextParseProgressPercent(0), 10)
  assert.ok(nextParseProgressPercent(50) > 50)
  assert.equal(nextParseProgressPercent(99), 92)
})
