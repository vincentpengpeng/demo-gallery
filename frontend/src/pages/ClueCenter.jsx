import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

export default function ClueCenter() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    title: '',
    content_type: 'text',
    raw_text: '',
    translated_text: '',
    source_platform: '',
    source_account: '',
    source_link: '',
    published_at: '',
    image_url: '',
    submitted_by: '',
  })
  const [file, setFile] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState('')
  const [ocrBusy, setOcrBusy] = useState(false)
  const [transBusy, setTransBusy] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  // 粘贴截图 → OCR 识别文字填入原文 + 保留图片用于出处追踪（反向识图）
  async function handlePaste(e) {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const fileObj = item.getAsFile()
        setFile(fileObj)                       // 保留截图，提交后用于图片溯源
        setForm((f) => ({ ...f, content_type: 'image' }))
        setOcrBusy(true)
        setMsg('正在 OCR 识别截图中的文字...')
        try {
          const res = await api.ocr(fileObj)
          if (res.ok && res.text) {
            setForm((f) => ({ ...f, raw_text: res.text }))
            setMsg(`OCR 识别完成，已填入原文（${res.text.length} 字符），截图将同时用于图片溯源。可编辑修正。`)
          } else {
            setMsg(`OCR 识别完成但文字为空；截图已保留用于图片溯源。${res.msg || ''}`)
          }
        } catch (err) {
          setMsg(`OCR 失败：${err.message}（截图仍保留用于图片溯源）`)
        } finally {
          setOcrBusy(false)
        }
        break
      }
    }
  }

  // 自动翻译：LLM 把原文翻译成中文
  async function handleTranslate() {
    if (!form.raw_text.trim()) { setMsg('请先填写原文内容'); return }
    setTransBusy(true)
    setMsg('正在调用 LLM 翻译成中文...')
    try {
      const res = await api.translate(form.raw_text)
      if (res.ok && res.translated) {
        setForm((f) => ({ ...f, translated_text: res.translated }))
        setMsg('翻译完成，已填入中文翻译。')
      } else {
        setMsg('翻译失败，请稍后重试。')
      }
    } catch (err) {
      setMsg(`翻译失败：${err.message}`)
    } finally {
      setTransBusy(false)
    }
  }

  async function submit(e) {
    e.preventDefault()
    setSubmitting(true)
    setMsg('')
    try {
      const fd = new FormData()
      Object.entries(form).forEach(([k, v]) => fd.append(k, v))
      if (file) fd.append('media', file)
      const out = await api.createClue(fd)
      setMsg(`线索已接收：${out.clue_no}，已启动自动核查流水线（环节2-8）...`)
      setTimeout(() => navigate(`/cases/${out.case_id}?auto=1`), 1500)
    } catch (err) {
      setMsg(`提交失败：${err.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  const inputStyle = {
    width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #d1d5db',
    fontSize: 13, outline: 'none',
  }
  const labelStyle = { display: 'block', fontSize: 13, color: '#374151', marginBottom: 6, fontWeight: 500 }

  return (
    <div style={{ maxWidth: 860 }}>
      <h2 style={{ fontSize: 20, marginBottom: 4 }}>线索中心 · 新建线索</h2>
      <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 20 }}>
        提交需要核查的海外涉华信息，系统将自动创建核查任务并推进 9 环节流程
      </p>

      <form onSubmit={submit} style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: 24 }}>
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>线索标题 *</label>
          <input style={inputStyle} value={form.title} onChange={set('title')} placeholder={'如：微信群流传"美日加军演，航母全出动，中国要怕了"'} />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>内容类型</label>
          <select style={inputStyle} value={form.content_type} onChange={set('content_type')}>
            <option value="text">文字内容</option>
            <option value="link">网页链接</option>
            <option value="image">图片 / 截图</option>
            <option value="video">视频（转写后走文字流程）</option>
            <option value="audio">音频（转写后走文字流程）</option>
          </select>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>
            原文内容（外文原文或截图）*
            <span style={{ fontWeight: 400, color: '#9ca3af', marginLeft: 8, fontSize: 11 }}>
              支持直接粘贴截图（Ctrl+V）自动识别文字
            </span>
          </label>
          <textarea
            style={{ ...inputStyle, minHeight: 100, resize: 'vertical' }}
            value={form.raw_text}
            onChange={set('raw_text')}
            onPaste={handlePaste}
            placeholder={'粘贴待核查的原文或截图（Ctrl+V）\n也可以直接输入外文，系统将自动拆解事实主张'}
          />
          {ocrBusy && <div style={{ fontSize: 12, color: '#2563eb', marginTop: 4 }}>OCR 识别中...</div>}
        </div>

        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <label style={labelStyle}>中文翻译（可留空，自动翻译）</label>
            <button type="button" onClick={handleTranslate} disabled={transBusy || !form.raw_text.trim()}
              style={{
                padding: '5px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
                border: '1px solid #2563eb', background: '#fff', color: '#2563eb',
                opacity: transBusy || !form.raw_text.trim() ? 0.5 : 1,
              }}>
              {transBusy ? '翻译中...' : '调用 LLM 翻译成中文'}
            </button>
          </div>
          <textarea style={{ ...inputStyle, minHeight: 60, resize: 'vertical' }} value={form.translated_text} onChange={set('translated_text')} placeholder="中文翻译（留空则在拆解时自动翻译）" />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>来源平台</label>
            <input style={inputStyle} value={form.source_platform} onChange={set('source_platform')} placeholder="如：X / Telegram / 微信" />
          </div>
          <div>
            <label style={labelStyle}>来源账号</label>
            <input style={inputStyle} value={form.source_account} onChange={set('source_account')} placeholder="如：@GlobalNewsNow" />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>原始链接</label>
            <input style={inputStyle} value={form.source_link} onChange={set('source_link')} placeholder="https://..." />
          </div>
          <div>
            <label style={labelStyle}>发布时间</label>
            <input style={inputStyle} value={form.published_at} onChange={set('published_at')} placeholder="如：2025-04-28 10:24" />
          </div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>图片公开链接（识图用，可选但推荐）</label>
          <input style={inputStyle} value={form.image_url} onChange={set('image_url')} placeholder="https://...（图片直链，用于反向搜图溯源）" />
          <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>
            填了公开图片链接可直接识图；只上传本地图片时，系统会自动经 GitHub 图床转成公开链接
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>提交人</label>
            <input style={inputStyle} value={form.submitted_by} onChange={set('submitted_by')} placeholder="姓名" />
          </div>
          <div>
            <label style={labelStyle}>上传图片 / 截图（用于图片溯源）</label>
            <input type="file" accept="image/*" onChange={(e) => {
              const f = e.target.files[0]
              setFile(f)
              if (f) setForm((prev) => ({ ...prev, content_type: 'image' }))
            }} style={{ fontSize: 13, padding: '8px 0' }} />
            {file && (
              <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                <img src={URL.createObjectURL(file)} alt="截图预览"
                  style={{ width: 64, height: 48, objectFit: 'cover', borderRadius: 6, border: '1px solid #e5e7eb' }} />
                <span style={{ fontSize: 11, color: '#059669' }}>已选图片：提交后将自动上传图床并做反向识图溯源</span>
              </div>
            )}
            <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>
              提示：也可直接在原文框按 Ctrl+V 粘贴截图（自动 OCR + 保留图片溯源）
            </div>
          </div>
        </div>

        <button type="submit" disabled={submitting || !form.raw_text.trim()}
          style={{
            width: '100%', padding: 12, background: '#2563eb', color: '#fff', border: 'none',
            borderRadius: 8, fontSize: 14, cursor: 'pointer', opacity: submitting ? 0.6 : 1,
          }}>
          {submitting ? '提交中...' : '提交线索，创建核查任务'}
        </button>
        {msg && <div style={{ marginTop: 12, fontSize: 13, color: '#059669' }}>{msg}</div>}
      </form>
    </div>
  )
}
