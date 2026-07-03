import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildVideoInfoTags,
  formatCount,
  qualityButtonMeta,
  qualitySizeLabel,
} from './videoInfo.js'

test('formatCount renders compact Chinese count labels', () => {
  assert.equal(formatCount(9800), '9800')
  assert.equal(formatCount(12500), '1.3万')
  assert.equal(formatCount(120000000), '1.2亿')
})

test('qualitySizeLabel renders approximate size or unknown fallback', () => {
  assert.equal(qualitySizeLabel({ filesize: '128 MB' }), '约 128 MB')
  assert.equal(qualitySizeLabel({ filesize: '' }), '大小未知')
  assert.equal(qualitySizeLabel(null), '大小未知')
})

test('qualityButtonMeta maps presets to parsed quality sizes', () => {
  const qualities = [
    { height: 1080, label: '1080p', filesize: '128 MB' },
    { height: 720, label: '720p', filesize: '64 MB' },
  ]

  assert.deepEqual(qualityButtonMeta({ key: 'best', label: '最佳画质' }, qualities), {
    label: '最佳画质',
    detail: '最高 1080p · 约 128 MB',
  })
  assert.deepEqual(qualityButtonMeta({ key: '720p', label: '720P', height: 720 }, qualities), {
    label: '720P',
    detail: '约 64 MB',
  })
})

test('buildVideoInfoTags creates rich metadata tags from parsed info', () => {
  const tags = buildVideoInfoTags({
    extractor: 'BiliBili',
    uploader: '作者',
    duration: 3661,
    qualities: [{ label: '1080p' }, { label: '720p' }],
    subtitles: ['zh-Hans', 'en'],
    view_count: 12500,
    id: 'BV123',
  })

  assert.deepEqual(
    tags.map((tag) => tag.text),
    ['平台 BiliBili', '作者 作者', '时长 1:01:01', '最高 1080p', '字幕 2 种', '播放 1.3万', 'ID BV123']
  )
  assert.ok(new Set(tags.map((tag) => tag.tone)).size > 3)
})
