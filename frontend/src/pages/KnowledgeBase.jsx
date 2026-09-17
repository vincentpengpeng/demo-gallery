import React from 'react'

const KB_ITEMS = [
  { type: '核查规范', title: '结论分类定义（8类）', desc: '真实 / 基本真实 / 缺乏语境 / 误导 / 基本错误 / 虚假 / 尚待核实 / 无法核查。证据不足禁止强下结论。' },
  { type: '核查规范', title: '证据分类', desc: '原始证据 / 独立佐证 / 反驳证据（必须主动检索，防确认偏误）/ 背景证据（不能单独替代直接证据）。' },
  { type: '方法', title: '多语种检索要点', desc: '同一主张生成中英文关键词分别检索；区分独立信源与转载信源；转载不计为独立证据。' },
  { type: '方法', title: '信源评价六维度', desc: '接近事件程度、专业性、独立性、透明度、时效性、利益相关度。' },
  { type: '信源', title: '高可信信源', desc: '政府/国际组织官方、科研机构、数据库、企业公告、路透/AP 等专业媒体、AFP Fact Check 等事实核查机构。' },
  { type: '信源', title: '高可信信源', desc: '海外社交平台帖子：需核对账号真实性、发布时间、是否被截图断章取义。' },
  { type: '案例', title: '旧图新用识别', desc: '对图片做反向搜图，比对最早出现时间与当前传播语境；原图删除后不保证找到源头。' },
  { type: '案例', title: '责任闭环', desc: '智能体提高证据搜集效率；成员承担复核责任；指导老师确认最终结论；AI 不直接回答真假。' },
]

export default function KnowledgeBase() {
  return (
    <div>
      <h2 style={{ fontSize: 20, marginBottom: 4 }}>知识库</h2>
      <p style={{ color: '#6b7280', fontSize: 13, marginBottom: 20 }}>
        核查规范、检索方法、常用信源与历史案例沉淀
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {KB_ITEMS.map((k, i) => (
          <div key={i} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 16 }}>
            <span style={{ fontSize: 11, color: '#2563eb', background: '#eff6ff', padding: '2px 10px', borderRadius: 8 }}>{k.type}</span>
            <div style={{ fontSize: 14, fontWeight: 600, margin: '8px 0 4px' }}>{k.title}</div>
            <div style={{ fontSize: 12, color: '#6b7280', lineHeight: 1.6 }}>{k.desc}</div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 16, fontSize: 12, color: '#9ca3af' }}>
        说明：知识库当前为内置示例，正式版将支持案例自动沉淀与检索（结案归档后回写）。
      </div>
    </div>
  )
}
