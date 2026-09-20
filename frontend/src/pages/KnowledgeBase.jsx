import React, { useEffect, useState } from 'react'
import { api } from '../api/client.js'

// 默认演示数据（首次加载时写入 localStorage，之后用户增删改都保存在本地）
const DEFAULT_KB = [
  { type: '核查规范', title: '结论分类定义（8类）', desc: '真实 / 基本真实 / 缺乏语境 / 误导 / 基本错误 / 虚假 / 尚待核实 / 无法核查。证据不足禁止强下结论。' },
  { type: '核查规范', title: '指控表述核查主线', desc: '外媒/人权组织的定性、比喻、断言（如"常态化治理工具""监狱"）须作为核查主线，独立判定是否有证据支撑，不得与政策事实混为一谈。' },
  { type: '核查规范', title: '证据分类', desc: '原始证据 / 独立佐证 / 反驳证据（必须主动检索，防确认偏误）/ 背景证据（不能单独替代直接证据）。' },
  { type: '核查规范', title: '证据不足的处置', desc: '官方文件只支持事实层，不能单独支撑指控层；证据链不足时输出"尚待核实"或"无法核查"，不凭立场臆断。' },
  { type: '核查方法', title: '多语种检索要点', desc: '同一主张生成中英文关键词分别检索；区分独立信源与转载信源；转载不计为独立证据。' },
  { type: '核查方法', title: '关键词生成规则', desc: '关键词须覆盖指控性表述的核心用语（如"边境管控 监狱 人权组织"），中英分列、不得混用；按"含汉字"判定语言方向。' },
  { type: '核查方法', title: '信源评价六维度', desc: '接近事件程度、专业性、涉华表述准确性、立场倾向、透明度、时效性。' },
  { type: '核查方法', title: '旧图新用识别', desc: '对图片做反向搜图，比对最早出现时间与当前传播语境；原图删除后不保证找到源头。' },
  { type: '信源分级', title: '高可信信源', desc: '政府/国际组织官方、科研机构、数据库、企业公告、路透/AP 等专业媒体、AFP Fact Check 等事实核查机构。' },
  { type: '信源分级', title: '中可信信源', desc: '主流商业媒体、权威智库报告、行业专业媒体；需结合信源6维评分综合判断。' },
  { type: '信源分级', title: '低可信信源', desc: '海外社交平台帖子（需核对账号真实性、发布时间、是否截图断章取义）；外媒官方喉舌（VOA/RFA/DW 等）涉华表述需特别警惕。' },
  { type: '信源分级', title: '外媒官方喉舌标记', desc: 'VOA、RFA、DW、自由欧洲电台等由政府资助的对外传播媒体，涉华报道立场倾向明显，证据引用时标红提示。' },
  { type: '典型案例', title: '案例：出入境新规与人权组织指控', desc: '人权组织称中国将边控变成"常态化治理工具"、边境成为"数百万人的监狱"。核查结论：事实层（新规发布）属实，指控层缺乏证据支撑，结论"误导/高置信度"。' },
  { type: '典型案例', title: '案例：旧图新用类谣言', desc: '某外媒将数年前旧照片配文为近期事件。反向识图比对最早发布时间后判定"虚假"，附原始出处时间线。' },
  { type: '典型案例', title: '案例：数据断章取义', desc: '外媒引用统计数据时省略年份与口径。核查发现其引用对象为历史峰值，与现行情况不符，结论"缺乏语境"。' },
  { type: '典型案例', title: '责任闭环', desc: '智能体提高证据搜集效率；成员承担复核责任；指导老师确认最终结论；AI 不直接回答真假。' },
]

const SECTION_COLORS = {
  '核查规范': { color: '#2563eb', bg: '#eff6ff' },
  '核查方法': { color: '#d97706', bg: '#fef3c7' },
  '信源分级': { color: '#059669', bg: '#ecfdf5' },
  '典型案例': { color: '#dc2626', bg: '#fef2f2' },
}

const STORAGE_KEY = 'zhentan_kb_items'

function loadItems() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch (e) { /* ignore */ }
  return DEFAULT_KB
}

export default function KnowledgeBase() {
  const [items, setItems] = useState(loadItems)
  const [filterType, setFilterType] = useState('all')
  const [keyword, setKeyword] = useState('')
  const [doneCount, setDoneCount] = useState(0)

  // 弹窗状态：null=关闭，'add'=新增，item=编辑中条目
  const [modal, setModal] = useState(null)
  const [viewing, setViewing] = useState(null)   // 查看详情的条目
  const [form, setForm] = useState({ type: '核查规范', title: '', desc: '' })
  const [saveMsg, setSaveMsg] = useState('')

  useEffect(() => {
    api.listCases().then((list) => setDoneCount((list || []).filter((c) => c.status === 'done').length)).catch(() => {})
  }, [])

  // 持久化到 localStorage
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)) } catch (e) { /* ignore */ }
  }, [items])

  const types = ['核查规范', '核查方法', '信源分级', '典型案例']

  let list = items
  if (filterType !== 'all') list = list.filter((k) => k.type === filterType)
  if (keyword) list = list.filter((k) => (k.title + k.desc).toLowerCase().includes(keyword.toLowerCase()))

  const openAdd = () => {
    setForm({ type: filterType !== 'all' ? filterType : '核查规范', title: '', desc: '' })
    setModal('add')
  }
  const openEdit = (item) => {
    setForm({ type: item.type, title: item.title, desc: item.desc })
    setModal(item)
  }
  const openView = (item) => setViewing(item)

  const saveItem = () => {
    if (!form.title.trim() || !form.desc.trim()) {
      setSaveMsg('标题和内容不能为空')
      return
    }
    if (modal === 'add') {
      setItems([{ ...form, title: form.title.trim(), desc: form.desc.trim() }, ...items])
    } else {
      setItems(items.map((k) => (k === modal ? { ...k, ...form, title: form.title.trim(), desc: form.desc.trim() } : k)))
    }
    setModal(null)
    setSaveMsg('')
  }

  const deleteItem = (item) => {
    if (!window.confirm(`确定删除知识条目「${item.title}」？`)) return
    setItems(items.filter((k) => k !== item))
  }

  const resetDemo = () => {
    if (!window.confirm('恢复为默认演示数据？当前修改会丢失。')) return
    setItems(DEFAULT_KB)
    try { localStorage.removeItem(STORAGE_KEY) } catch (e) { /* ignore */ }
  }

  const statCounts = {}
  items.forEach((k) => { statCounts[k.type] = (statCounts[k.type] || 0) + 1 })

  const inputStyle = {
    width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db',
    fontSize: 13, boxSizing: 'border-box', marginBottom: 10,
  }

  return (
    <div>
      {/* 顶部：标题 + 操作按钮 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <h2 style={{ fontSize: 20, marginBottom: 4 }}>知识库</h2>
          <p style={{ color: '#6b7280', fontSize: 13 }}>
            核查规范、检索方法、信源分级与历史案例沉淀
            <span style={{ color: '#d97706', marginLeft: 8 }}>（已沉淀结案案例 {doneCount} 个）</span>
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={resetDemo} style={{ padding: '8px 14px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: '1px solid #d1d5db', background: '#fff', color: '#6b7280' }}>
            恢复默认
          </button>
          <button onClick={openAdd} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: 'none', background: '#2563eb', color: '#fff' }}>
            + 新增条目
          </button>
        </div>
      </div>

      {/* 筛选栏 */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button onClick={() => setFilterType('all')}
            style={{ padding: '6px 14px', borderRadius: 16, fontSize: 12, cursor: 'pointer', border: '1px solid #d1d5db', background: filterType === 'all' ? '#2563eb' : '#fff', color: filterType === 'all' ? '#fff' : '#374151' }}>
            全部（{items.length}）
          </button>
          {types.map((t) => (
            <button key={t} onClick={() => setFilterType(t)}
              style={{ padding: '6px 14px', borderRadius: 16, fontSize: 12, cursor: 'pointer', border: '1px solid #d1d5db', background: filterType === t ? '#2563eb' : '#fff', color: filterType === t ? '#fff' : '#374151' }}>
              {t}（{statCounts[t] || 0}）
            </button>
          ))}
        </div>
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索标题 / 内容…"
          style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13, width: 240, marginLeft: 'auto' }}
        />
      </div>

      {/* 条目网格 */}
      {types.filter((t) => filterType === 'all' || t === filterType).map((sec) => {
        const secItems = list.filter((k) => k.type === sec)
        if (secItems.length === 0) return null
        const sc = SECTION_COLORS[sec]
        return (
          <div key={sec} style={{ marginBottom: 22 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: sc.color }}>{sec}</span>
              <div style={{ flex: 1, height: 1, background: '#e5e7eb' }} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {secItems.map((k, i) => (
                <div key={i} style={{ background: '#fff', border: '1px solid #e5e7eb', borderLeft: `3px solid ${sc.color}`, borderRadius: 10, padding: 14, cursor: 'pointer' }}
                  onClick={() => openView(k)}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 6 }}>{k.title}</div>
                    <div style={{ display: 'flex', gap: 6, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => openEdit(k)} title="编辑"
                        style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', border: '1px solid #d1d5db', background: '#fff', color: '#374151' }}>编辑</button>
                      <button onClick={() => deleteItem(k)} title="删除"
                        style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626' }}>删除</button>
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.7, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{k.desc}</div>
                </div>
              ))}
            </div>
          </div>
        )
      })}
      {list.length === 0 && (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 24, textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
          暂无匹配条目，可点击右上角"新增条目"添加
        </div>
      )}

      {/* 查看详情弹窗 */}
      {viewing && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }} onClick={() => setViewing(null)}>
          <div style={{ background: '#fff', borderRadius: 14, padding: 24, maxWidth: 520, width: '90%', boxShadow: '0 20px 50px rgba(0,0,0,0.25)' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 11, color: SECTION_COLORS[viewing.type].color, background: SECTION_COLORS[viewing.type].bg, padding: '3px 12px', borderRadius: 10 }}>{viewing.type}</span>
              <button onClick={() => setViewing(null)} style={{ border: 'none', background: 'none', fontSize: 18, cursor: 'pointer', color: '#9ca3af' }}>×</button>
            </div>
            <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 12 }}>{viewing.title}</div>
            <div style={{ fontSize: 13.5, color: '#4b5563', lineHeight: 1.8 }}>{viewing.desc}</div>
            <div style={{ marginTop: 18, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => { setViewing(null); openEdit(viewing) }} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: '1px solid #d1d5db', background: '#fff', color: '#374151' }}>编辑</button>
              <button onClick={() => setViewing(null)} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: 'none', background: '#2563eb', color: '#fff' }}>关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* 新增/编辑弹窗 */}
      {modal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1001 }} onClick={() => setModal(null)}>
          <div style={{ background: '#fff', borderRadius: 14, padding: 24, maxWidth: 520, width: '90%', boxShadow: '0 20px 50px rgba(0,0,0,0.25)' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 16 }}>
              {modal === 'add' ? '新增知识条目' : '编辑知识条目'}
            </div>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>分类</div>
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}
              style={{ ...inputStyle, width: '100%' }}>
              {types.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>标题</div>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="请输入条目标题"
              style={inputStyle} />
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>内容</div>
            <textarea value={form.desc} onChange={(e) => setForm({ ...form, desc: e.target.value })} placeholder="请输入条目内容"
              rows={5} style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }} />
            {saveMsg && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{saveMsg}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 6 }}>
              <button onClick={() => setModal(null)} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: '1px solid #d1d5db', background: '#fff', color: '#374151' }}>取消</button>
              <button onClick={saveItem} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: 'none', background: '#2563eb', color: '#fff' }}>
                {modal === 'add' ? '保存' : '保存修改'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
