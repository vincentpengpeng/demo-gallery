import React, { useEffect, useState } from 'react'
import { api } from '../api/client.js'

// 演示知识库：内置核查规范、方法与示例案例，便于演示效果
const KB_SECTIONS = [
  {
    type: '核查规范',
    color: '#2563eb', bg: '#eff6ff',
    items: [
      { title: '结论分类定义（8类）', desc: '真实 / 基本真实 / 缺乏语境 / 误导 / 基本错误 / 虚假 / 尚待核实 / 无法核查。证据不足禁止强下结论。' },
      { title: '指控表述核查主线', desc: '外媒/人权组织的定性、比喻、断言（如"常态化治理工具""监狱"）须作为核查主线，独立判定是否有证据支撑，不得与政策事实混为一谈。' },
      { title: '证据分类', desc: '原始证据 / 独立佐证 / 反驳证据（必须主动检索，防确认偏误）/ 背景证据（不能单独替代直接证据）。' },
      { title: '证据不足的处置', desc: '官方文件只支持事实层，不能单独支撑指控层；证据链不足时输出"尚待核实"或"无法核查"，不凭立场臆断。' },
    ],
  },
  {
    type: '核查方法',
    color: '#d97706', bg: '#fef3c7',
    items: [
      { title: '多语种检索要点', desc: '同一主张生成中英文关键词分别检索；区分独立信源与转载信源；转载不计为独立证据。' },
      { title: '关键词生成规则', desc: '关键词须覆盖指控性表述的核心用语（如"边境管控 监狱 人权组织"），中英分列、不得混用；按"含汉字"判定语言方向。' },
      { title: '信源评价六维度', desc: '接近事件程度、专业性、涉华表述准确性、立场倾向、透明度、时效性。' },
      { title: '旧图新用识别', desc: '对图片做反向搜图，比对最早出现时间与当前传播语境；原图删除后不保证找到源头。' },
    ],
  },
  {
    type: '信源分级',
    color: '#059669', bg: '#ecfdf5',
    items: [
      { title: '高可信信源', desc: '政府/国际组织官方、科研机构、数据库、企业公告、路透/AP 等专业媒体、AFP Fact Check 等事实核查机构。' },
      { title: '中可信信源', desc: '主流商业媒体、权威智库报告、行业专业媒体；需结合信源6维评分综合判断。' },
      { title: '低可信信源', desc: '海外社交平台帖子（需核对账号真实性、发布时间、是否截图断章取义）；外媒官方喉舌（VOA/RFA/DW 等）涉华表述需特别警惕。' },
      { title: '外媒官方喉舌标记', desc: 'VOA、RFA、DW、自由欧洲电台等由政府资助的对外传播媒体，涉华报道立场倾向明显，证据引用时标红提示。' },
    ],
  },
  {
    type: '典型案例',
    color: '#dc2626', bg: '#fef2f2',
    items: [
      { title: '案例：出入境新规与人权组织指控', desc: '人权组织称中国将边控变成"常态化治理工具"、边境成为"数百万人的监狱"。核查结论：事实层（新规发布）属实，指控层缺乏证据支撑，结论"误导/高置信度"。' },
      { title: '案例：旧图新用类谣言', desc: '某外媒将数年前旧照片配文为近期事件。反向识图比对最早发布时间后判定"虚假"，附原始出处时间线。' },
      { title: '案例：数据断章取义', desc: '外媒引用统计数据时省略年份与口径。核查发现其引用对象为历史峰值，与现行情况不符，结论"缺乏语境"。' },
      { title: '责任闭环', desc: '智能体提高证据搜集效率；成员承担复核责任；指导老师确认最终结论；AI 不直接回答真假。' },
    ],
  },
]

export default function KnowledgeBase() {
  const [doneCount, setDoneCount] = useState(0)
  useEffect(() => {
    api.listCases().then((list) => setDoneCount((list || []).filter((c) => c.status === 'done').length)).catch(() => {})
  }, [])

  return (
    <div>
      <h2 style={{ fontSize: 20, marginBottom: 4 }}>知识库</h2>
      <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 20 }}>
        核查规范、检索方法、信源分级与历史案例沉淀
        <span style={{ color: '#d97706', marginLeft: 8 }}>（已沉淀结案案例 {doneCount} 个）</span>
      </p>

      {KB_SECTIONS.map((sec) => (
        <div key={sec.type} style={{ marginBottom: 22 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: sec.color }}>{sec.type}</span>
            <div style={{ flex: 1, height: 1, background: '#e5e7eb' }} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {sec.items.map((k, i) => (
              <div key={i} style={{ background: '#fff', border: '1px solid #e5e7eb', borderLeft: `3px solid ${sec.color}`, borderRadius: 10, padding: 14 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 6 }}>{k.title}</div>
                <div style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.7 }}>{k.desc}</div>
              </div>
            ))}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 16, fontSize: 12, color: '#9ca3af' }}>
        说明：当前展示演示知识库内容。正式版将支持结案案例自动沉淀入库与语义检索（结案归档后回写）。
      </div>
    </div>
  )
}
