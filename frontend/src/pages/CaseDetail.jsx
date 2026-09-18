import React, { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api, STAGES, mediaUrl } from '../api/client.js'
import ConclusionBadge from '../components/ConclusionBadge.jsx'

export default function CaseDetail() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const [caseData, setCaseData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [polling, setPolling] = useState(false)   // 是否在轮询自动核查进度

  async function load() {
    try {
      const data = await api.getCase(id)
      setCaseData(data)
      // 完成条件：已结案，或流水线走完（环节8报告已生成）→ 停止轮询
      const finished = data.status === 'done' || data.status === 'reviewing' ||
        (data.running_log && data.running_log.length >= 7) || data.stage >= 8
      if (finished) setPolling(false)
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [id])

  // 从线索中心跳转（?auto=1）：页面就绪后自动触发流水线并进入轮询
  useEffect(() => {
    if (params.get('auto') === '1' && caseData && caseData.status !== 'done') {
      api.auto(id).then(() => {
        setPolling(true)
        load()
        // 清除参数，避免刷新页面重复触发
        setParams({}, { replace: true })
      }).catch(() => {
        // 若已 running（重复触发被后端拒），直接进入轮询
        setPolling(true)
        load()
      })
    }
  }, [caseData, params, id])

  // 执行中：手动触发过 auto（polling）或后端正在 running（status 会随环节变化，不能只依赖它）
  const isRunning = caseData?.status === 'running'
  const isExecuting = polling || isRunning
  const notFinished = !caseData || caseData.status === 'running' ||
    caseData.status === 'received' || caseData.status === 'screening' ||
    caseData.status === 'decomposing' || caseData.status === 'searching' ||
    caseData.status === 'tracing' || caseData.status === 'verifying' ||
    caseData.status === 'evaluating' || caseData.status === 'reporting'
  const shouldPoll = (polling || isRunning) && notFinished
  useEffect(() => {
    if (!shouldPoll) return
    const timer = setInterval(() => { load() }, 2000)
    return () => clearInterval(timer)
  }, [shouldPoll, id])

  async function run(fn, label) {
    setBusy(true)
    setErr('')
    try {
      await fn(id)
      await load()
    } catch (e) {
      setErr(`${label}失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <div style={{ color: '#6b7280' }}>加载中...</div>
  if (err && !caseData) return <div style={{ color: '#dc2626' }}>{err}</div>
  if (!caseData) return <div style={{ color: '#6b7280' }}>案件不存在</div>

  const c = caseData
  const stageIdx = Math.max(0, Math.min(c.stage, 9) - 1)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 4 }}>
            核查任务 &gt; 案件详情 &gt; 智能核查工作台
          </div>
          <h2 style={{ fontSize: 19, marginBottom: 4 }}>{c.title}</h2>
          <div style={{ fontSize: 12, color: '#9ca3af' }}>
            {c.case_no} · 来源 {c.clue.source_platform || '-'} · 提交人 {c.clue.submitted_by || '-'}
            {c.clue.published_at && <> · 发布时间 {c.clue.published_at}</>}
          </div>
        </div>
        <span style={{
          padding: '4px 14px', borderRadius: 12, fontSize: 13,
          background: c.status === 'done' ? '#ecfdf5' : '#eff6ff',
          color: c.status === 'done' ? '#059669' : '#2563eb',
        }}>{c.stage_name}</span>
      </div>

      {/* 9 环节流水线节点（当前环节脉冲动画） */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '14px 18px' }}>
        {STAGES.map((s, i) => {
          const isCur = i === stageIdx && isExecuting
          return (
            <div key={s.id} style={{ flex: 1, textAlign: 'center' }}>
              <div style={{
                width: 26, height: 26, margin: '0 auto 6px', borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11,
                background: i < stageIdx ? '#2563eb' : i === stageIdx ? (isExecuting ? '#f59e0b' : '#059669') : '#e5e7eb',
                color: i <= stageIdx ? '#fff' : '#9ca3af',
                animation: isCur ? 'ztPulse 1.2s ease-in-out infinite' : 'none',
                boxShadow: isCur ? '0 0 0 4px rgba(245,158,11,0.25)' : 'none',
              }}>{i < stageIdx ? '✓' : s.id}</div>
              <div style={{
                fontSize: 10, color: isCur ? '#f59e0b' : i === stageIdx ? '#059669' : '#9ca3af',
                fontWeight: isCur ? 700 : 400,
              }}>{s.name}</div>
            </div>
          )
        })}
      </div>
      <style>{`
        @keyframes ztPulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.15); }
        }
        @keyframes ztSpin {
          to { transform: rotate(360deg); }
        }
        @keyframes ztFadeIn {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* 类流式运行状态条 */}
      {isExecuting && (
        <div style={{
          background: 'linear-gradient(90deg, #ecfdf5, #eff6ff)', border: '1px solid #a7f3d0',
          borderRadius: 10, padding: '12px 18px', marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <Spinner />
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#047857' }}>
              自动核查进行中，各环节结果将实时展示…
            </div>
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>
              已完成 {c.running_log?.length || 0}/7 个环节 · 页面每 2 秒自动刷新
            </div>
          </div>
        </div>
      )}

      {/* 逐环节操作 */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
        <button
          onClick={async () => {
            setBusy(true); setErr('')
            try {
              await api.auto(id)
              setPolling(true)   // 强制进入轮询，实时刷新进度
              await load()
            } catch (e) {
              setErr(`自动核查启动失败：${e.message}`)
            } finally {
              setBusy(false)
            }
          }}
          disabled={busy || c.status === 'done' || c.status === 'reviewing' || isExecuting}
          style={{
            padding: '10px 22px', borderRadius: 8, fontSize: 14, cursor: 'pointer',
            border: 'none', background: '#059669', color: '#fff', fontWeight: 600,
            opacity: busy || c.status === 'done' || c.status === 'reviewing' || isExecuting ? 0.5 : 1,
          }}>
          {isExecuting ? '自动核查中...' : '一键自动核查（环节2-8）'}
        </button>
        <ActionBtn onClick={() => run(api.screening, '价值初筛')} disabled={busy || c.stage > 2}>价值初筛</ActionBtn>
        <ActionBtn onClick={() => run(api.decompose, '主张拆解')} disabled={busy || c.stage > 3}>主张拆解</ActionBtn>
        <ActionBtn onClick={() => run(api.search, '多语种检索')} disabled={busy || c.stage > 4}>多语种检索</ActionBtn>
        <ActionBtn onClick={() => run(api.trace, '出处追踪')} disabled={busy || c.stage > 5}>出处追踪</ActionBtn>
        <ActionBtn onClick={() => run(api.verify, '交叉验证')} disabled={busy || c.stage > 6}>交叉验证</ActionBtn>
        <ActionBtn onClick={() => run(api.evaluate, '信源评价')} disabled={busy || c.stage > 7}>信源评价</ActionBtn>
        <ActionBtn onClick={() => run(api.report, '报告生成')} disabled={busy || c.stage > 8}>生成报告</ActionBtn>
      </div>
      {err && <div style={{ color: '#dc2626', fontSize: 13, marginBottom: 12 }}>{err}</div>}
      {busy && <div style={{ color: '#2563eb', fontSize: 13, marginBottom: 12 }}>处理中...</div>}

      {/* 自动核查进度（最新一条高亮动画） */}
      {(isExecuting || (c.running_log && c.running_log.length > 0)) && (
        <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '14px 18px', marginBottom: 16 }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
            自动核查流水线
            {isExecuting && <span style={{ fontSize: 11, color: '#f59e0b', background: '#fef3c7', padding: '2px 10px', borderRadius: 8 }}>执行中</span>}
          </div>
          {c.running_log.map((s, i) => {
            const isLatest = isExecuting && i === c.running_log.length - 1
            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', fontSize: 13,
                borderBottom: i < c.running_log.length - 1 ? '1px dashed #f3f4f6' : 'none',
                animation: isLatest ? 'ztFadeIn 0.5s ease' : 'none',
              }}>
                {isLatest && !s.ok ? (
                  <Spinner size={16} />
                ) : (
                  <span style={{
                    width: 18, height: 18, borderRadius: '50%', display: 'inline-flex',
                    alignItems: 'center', justifyContent: 'center', fontSize: 10,
                    background: s.ok ? '#059669' : '#d97706', color: '#fff',
                  }}>{s.ok ? '✓' : '!'}</span>
                )}
                <span style={{ color: '#374151', fontWeight: isLatest ? 600 : 400 }}>{s.name}</span>
                <span style={{ color: '#9ca3af', fontSize: 12 }}>{s.detail}</span>
              </div>
            )
          })}
          {!isExecuting && c.running_log.length >= 7 && (
            <div style={{ marginTop: 8, fontSize: 12, color: '#059669' }}>
              自动核查已完成（环节2-8），请进入下方「核查报告」进行人工审核。
            </div>
          )}
          {!isExecuting && c.running_log.length > 0 && c.running_log.length < 7 && (
            <div style={{ marginTop: 8, fontSize: 12, color: '#d97706' }}>
              自动核查进行中（已完成 {c.running_log.length}/7 个环节），继续等待后续环节完成…
            </div>
          )}
        </div>
      )}

      {/* 待核查材料 */}
      <Section title="待核查材料" sub="来自海外平台的原始内容及相关信息">
        <div style={{ display: 'flex', gap: 20 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: '#374151', marginBottom: 6, fontWeight: 600 }}>原文</div>
            <div style={{ background: '#f9fafb', borderRadius: 8, padding: 12, fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
              {c.clue.raw_text || '（无原文）'}
            </div>
            {c.clue.translated_text && (
              <>
                <div style={{ fontSize: 13, color: '#374151', margin: '10px 0 6px', fontWeight: 600 }}>中文翻译</div>
                <div style={{ background: '#f9fafb', borderRadius: 8, padding: 12, fontSize: 13, lineHeight: 1.6 }}>
                  {c.clue.translated_text}
                </div>
              </>
            )}
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 10 }}>
              账号：{c.clue.source_account || '-'} · 链接：
              {c.clue.source_link ? <a href={c.clue.source_link} target="_blank" rel="noreferrer" style={{ color: '#2563eb' }}>{c.clue.source_link.slice(0, 40)}</a> : '-'}
            </div>
          </div>
          {c.clue.media_path && (
            <div style={{ width: 220 }}>
              <img src={mediaUrl(c.clue.media_path)} alt="线索媒体"
                style={{ width: '100%', borderRadius: 8, border: '1px solid #e5e7eb' }} />
            </div>
          )}
        </div>
      </Section>

      {/* 价值初筛 */}
      {c.screening_result && Object.keys(c.screening_result).length > 0 && (
        <Section title="价值初筛" sub="判断是否进入核查">
          <div style={{ fontSize: 13, lineHeight: 1.8 }}>
            <span style={{
              padding: '3px 12px', borderRadius: 10, fontSize: 12, marginRight: 10,
              background: c.screening_result.passed ? '#ecfdf5' : '#fef3c7',
              color: c.screening_result.passed ? '#059669' : '#b45309',
            }}>{c.screening_result.passed ? '通过' : '暂缓'}</span>
            {c.screening_result.reason}
            {c.screening_result.focus && (
              <div style={{ color: '#374151', fontSize: 12, marginTop: 6 }}>
                议题方向：{c.screening_result.focus}
              </div>
            )}
            <div style={{ color: '#6b7280', fontSize: 12, marginTop: 6 }}>
              得分 {c.screening_result.score}/100
              {c.screening_result.hit_keywords && c.screening_result.hit_keywords.length > 0 &&
                <> · 命中关键词：{c.screening_result.hit_keywords.join('、')}</>}
              {c.screening_result.method && (
                <> · 判定方式：{c.screening_result.method === 'llm' ? 'LLM 智能判断' : c.screening_result.method === 'llm+keyword' ? 'LLM+关键词复核' : '关键词匹配'}</>
              )}
            </div>
          </div>
        </Section>
      )}

      {/* 主张拆解 */}
      {c.claims.length > 0 && (
        <Section title="事实主张拆解" sub="自动拆解核心主张（指控表述为核查主线），提取关键要素" fresh={true}>
          {c.claims.map((cl, i) => {
            const typeMeta = {
              allegation: { label: '指控表述', border: '#dc2626', bg: '#fef2f2', color: '#dc2626' },
              fact: { label: '事实主张', border: '#2563eb', bg: '#eff6ff', color: '#2563eb' },
              view: { label: '观点表达', border: '#d97706', bg: '#fef3c7', color: '#b45309' },
              emotion: { label: '情绪表达', border: '#9ca3af', bg: '#f3f4f6', color: '#6b7280' },
            }
            const meta = typeMeta[cl.type] || typeMeta.fact
            return (
              <div key={i} style={{
                background: '#f9fafb', borderRadius: 8, padding: 12, marginBottom: 10,
                borderLeft: `3px solid ${meta.border}`,
              }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 8,
                    background: meta.bg, color: meta.color, fontWeight: 600,
                  }}>
                    {meta.label}
                    {cl.type === 'allegation' && ' ★'}
                  </span>
                  <span style={{ fontSize: 13, fontWeight: cl.type === 'allegation' ? 600 : 400 }}>{cl.text}</span>
                </div>
                {cl.elements && Object.entries(cl.elements).filter(([, v]) => v).length > 0 && (
                  <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                    要素：{Object.entries(cl.elements).filter(([, v]) => v).map(([k, v]) => `${k}:${v}`).join(' | ')}
                  </div>
                )}
                {cl.type === 'allegation' && (
                  <div style={{ fontSize: 11, color: '#dc2626', marginTop: 6 }}>
                    ▲ 核查主线：本表述为对中方的指控/定性，将重点核查其是否有证据支撑
                  </div>
                )}
              </div>
            )
          })}
          {c.keywords && (c.keywords.zh || c.keywords.en) && (
            <div style={{ fontSize: 12, color: '#374151', background: '#eff6ff', borderRadius: 8, padding: 10 }}>
              检索关键词：中文「{c.keywords.zh || '-'}」 · 英文「{c.keywords.en || '-'}」
            </div>
          )}
        </Section>
      )}

      {/* 证据矩阵 */}
      {c.evidence.length > 0 && (
        <Section title="证据矩阵" sub="多源交叉验证，识别转载关系，评估证据可靠性" fresh={true}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ color: '#6b7280', textAlign: 'left' }}>
                <th style={{ padding: '8px 10px' }}>证据名称</th>
                <th style={{ padding: '8px 10px' }}>来源机构</th>
                <th style={{ padding: '8px 10px' }}>发布日期</th>
                <th style={{ padding: '8px 10px' }}>与主张关系</th>
                <th style={{ padding: '8px 10px' }}>信源类型</th>
                <th style={{ padding: '8px 10px' }}>可信度</th>
              </tr>
            </thead>
            <tbody>
              {c.evidence.map((e) => (
                <tr key={e.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '8px 10px', maxWidth: 200 }}>
                    {e.url ? (
                      <a href={e.url} target="_blank" rel="noreferrer" style={{ color: '#2563eb', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.name}</span>
                        <span style={{ fontSize: 10, background: '#eff6ff', color: '#2563eb', padding: '1px 6px', borderRadius: 6, flexShrink: 0 }}>↗</span>
                      </a>
                    ) : (
                      <span>{e.name}</span>
                    )}
                    {e.is_independent === 0 && <span style={{ fontSize: 10, color: '#b45309', marginLeft: 4 }}>(转载)</span>}
                  </td>
                  <td style={{ padding: '8px 10px' }}>{e.source_org}</td>
                  <td style={{ padding: '8px 10px' }}>{e.publish_date}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <RelBadge r={e.relation} />
                  </td>
                  <td style={{ padding: '8px 10px' }}>
                    {e.source_type?.includes('中方官方') ? (
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, background: '#ecfdf5', color: '#059669', fontWeight: 600 }}>{e.source_type}</span>
                    ) : e.source_type?.includes('中方媒体') ? (
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, background: '#eff6ff', color: '#2563eb', fontWeight: 600 }}>{e.source_type}</span>
                    ) : e.source_type?.includes('外媒官方喉舌') ? (
                      <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 8, background: '#fef2f2', color: '#dc2626', fontWeight: 600 }}>{e.source_type}</span>
                    ) : e.source_type}
                  </td>
                  <td style={{ padding: '8px 10px' }}>{e.reliability}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 8, fontSize: 11, color: '#9ca3af' }}>
            点击证据名称可跳转查看原网页（外部链接）
          </div>
          <div style={{ marginTop: 8, fontSize: 11, color: '#6b7280', background: '#f8fafc', borderRadius: 8, padding: '8px 12px', lineHeight: 1.6 }}>
            判定说明：证据与「指控表述」（对中方的定性/比喻）和「事实主张」（政策/事件事实）分层判定。
            官方文件等过程性证据可支持事实层（政策确实发布），但通常<b>不构成</b>对指控性表述的支持，除非其直接证明指控成立。
          </div>
          {c.verification_results && c.verification_results.warning && (
            <div style={{ marginTop: 10, background: '#fef3c7', color: '#b45309', fontSize: 12, padding: '8px 12px', borderRadius: 8 }}>
              {c.verification_results.warning}
            </div>
          )}
        </Section>
      )}

      {/* 出处追踪 */}
      {c.trace_results && c.trace_results.length > 0 && (
        <Section title="出处追踪" sub="反向搜图匹配结果（SerpAPI Google）">
          {c.trace_results.map((t, i) => (
            <div key={i} style={{ background: '#f9fafb', borderRadius: 8, padding: 12, marginBottom: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {t.matched_title || '未命名来源'}
                {t.matched_site && <span style={{ color: '#6b7280', fontWeight: 400, marginLeft: 8 }}>{t.matched_site}</span>}
              </div>
              {t.url && <a href={t.url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: '#2563eb', display: 'block', marginTop: 4 }}>{t.url.slice(0, 70)}</a>}
              {t.note && <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{t.note}</div>}
            </div>
          ))}
        </Section>
      )}

      {/* 信源评价 */}
      {c.source_evals.length > 0 && (
        <Section title="信源评价" sub="基于多维度评估信源可靠性，辅助判断结论" fresh={true}>
          {c.source_evals.map((e, i) => (
            <div key={i} style={{ background: '#f9fafb', borderRadius: 8, padding: 12, marginBottom: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ fontWeight: 600 }}>{e.name}</span>
                <span style={{
                  padding: '2px 10px', borderRadius: 8, fontSize: 12,
                  background: e.grade === 'A' ? '#ecfdf5' : e.grade === 'B' ? '#eff6ff' : '#fef3c7',
                  color: e.grade === 'A' ? '#059669' : e.grade === 'B' ? '#2563eb' : '#b45309',
                }}>评级 {e.grade}</span>
              </div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                {Object.entries(e.dimensions || {}).map(([k, v]) => `${k}:${v}`).join(' · ')}
              </div>
              {e.reason && <div style={{ fontSize: 12, color: '#374151', marginTop: 4 }}>{e.reason}</div>}
            </div>
          ))}
        </Section>
      )}

      {/* 报告（结构化） */}
      {c.report && (
        <Section title="核查报告" sub="AI 生成的初步报告，需人工审核确认" fresh={true}>
          {/* 1. 初步结论（按结论类型配色） */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, borderBottom: '1px solid #f3f4f6', paddingBottom: 12 }}>
            <span style={{ fontSize: 15, fontWeight: 700 }}>初步结论：</span>
            <ConclusionBadge conclusion={c.report.conclusion} />
            <span style={{ fontSize: 12, color: '#6b7280' }}>置信度：{c.report.confidence}</span>
          </div>
          {c.report.preliminary_conclusion && (
            <div style={{ fontSize: 13, lineHeight: 1.7, marginBottom: 12, color: '#374151' }}>
              {c.report.preliminary_conclusion}
            </div>
          )}

          {/* 2. 核查摘要 */}
          {c.report.summary && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>核查摘要</div>
              <div style={{ fontSize: 13, lineHeight: 1.7, background: '#f9fafb', borderRadius: 8, padding: 12, whiteSpace: 'pre-wrap' }}>
                {c.report.summary}
              </div>
            </div>
          )}

          {/* 3. 证据表 */}
          {c.report.evidence_table && c.report.evidence_table.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>证据表（{c.report.evidence_table.length} 条）</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ color: '#6b7280', textAlign: 'left' }}>
                    <th style={{ padding: '8px 10px' }}>证据</th>
                    <th style={{ padding: '8px 10px' }}>来源</th>
                    <th style={{ padding: '8px 10px' }}>日期</th>
                    <th style={{ padding: '8px 10px' }}>关系</th>
                    <th style={{ padding: '8px 10px' }}>可信度</th>
                    <th style={{ padding: '8px 10px' }}>链接</th>
                  </tr>
                </thead>
                <tbody>
                  {c.report.evidence_table.map((et, i) => (
                    <tr key={i} style={{ borderTop: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '8px 10px', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {et.name}
                      </td>
                      <td style={{ padding: '8px 10px' }}>{et.source || et.grade || '-'}</td>
                      <td style={{ padding: '8px 10px' }}>{et.date || '-'}</td>
                      <td style={{ padding: '8px 10px' }}><RelBadge r={et.relation || '待确认'} /></td>
                      <td style={{ padding: '8px 10px' }}>{et.reliability || '-'}</td>
                      <td style={{ padding: '8px 10px' }}>
                        {et.url ? (
                          <a href={et.url} target="_blank" rel="noreferrer" style={{ color: '#2563eb', textDecoration: 'none' }}>查看 ↗</a>
                        ) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 4. 来源链接 */}
          {c.report.source_links && c.report.source_links.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>来源链接（{c.report.source_links.length}）</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {c.report.source_links.map((sl, i) => (
                  <a key={i} href={sl.url} target="_blank" rel="noreferrer" style={{
                    fontSize: 12, color: '#2563eb', textDecoration: 'none',
                    background: '#f9fafb', padding: '8px 12px', borderRadius: 8,
                  }}>
                    {sl.title || sl.url}
                    {sl.source && <span style={{ color: '#9ca3af', marginLeft: 8 }}>{sl.source}</span>}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* 5. 证据缺口 */}
          {c.report.gaps && c.report.gaps.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>证据缺口</div>
              <div style={{ background: '#fef3c7', borderRadius: 8, padding: 10, fontSize: 12, color: '#b45309' }}>
                {c.report.gaps.map((g, i) => <div key={i} style={{ padding: '2px 0' }}>· {g}</div>)}
              </div>
            </div>
          )}

          {/* 6. 待确认事项 */}
          {c.report.pending_items && c.report.pending_items.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>待确认事项</div>
              <div style={{ background: '#eff6ff', borderRadius: 8, padding: 10, fontSize: 12, color: '#1d4ed8' }}>
                {c.report.pending_items.map((p, i) => <div key={i} style={{ padding: '2px 0' }}>· {p}</div>)}
              </div>
            </div>
          )}

          {/* 环节9：人工审核 */}
          <ReviewPanel caseData={c} onDone={load} />
        </Section>
      )}

      {/* 审核记录 */}
      {c.reviews.length > 0 && (
        <Section title="审核记录" sub="人工审核留痕">
          {c.reviews.map((r, i) => (
            <div key={i} style={{ fontSize: 12, color: '#374151', padding: '6px 0', borderBottom: '1px solid #f3f4f6' }}>
              {r.reviewer} · {r.action === 'approved' ? '通过' : r.action === 'revised' ? '修改' : '退回'} ·
              {r.comment || '（无意见）'}
              {r.check_items && r.check_items.length > 0 && <span style={{ color: '#6b7280' }}> · 已核 {r.check_items.length} 项</span>}
            </div>
          ))}
        </Section>
      )}
    </div>
  )
}

function ActionBtn({ children, onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: disabled ? 'not-allowed' : 'pointer',
      border: '1px solid #2563eb', background: '#fff', color: '#2563eb',
      opacity: disabled ? 0.4 : 1,
    }}>{children}</button>
  )
}

function Section({ title, sub, children, fresh }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: 18, marginBottom: 16,
      animation: fresh ? 'ztFadeIn 0.6s ease' : 'none',
    }}>
      <div style={{ fontWeight: 600, marginBottom: 2 }}>{title}</div>
      {sub && <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 12 }}>{sub}</div>}
      {children}
    </div>
  )
}

function Spinner({ size = 16 }) {
  return (
    <span style={{
      width: size, height: size, borderRadius: '50%', display: 'inline-block',
      border: `2px solid #a7f3d0`, borderTopColor: '#059669',
      animation: 'ztSpin 0.8s linear infinite',
    }} />
  )
}

function RelBadge({ r }) {
  const map = { 支持: '#059669', 反驳: '#dc2626', 背景: '#6b7280', 待确认: '#b45309' }
  return <span style={{ padding: '2px 8px', borderRadius: 8, fontSize: 11, background: '#f3f4f6', color: map[r] || '#374151' }}>{r}</span>
}

// 结论标签（共享组件，见 components/ConclusionBadge.jsx）

function ReviewPanel({ caseData, onDone }) {
  const [reviewer, setReviewer] = useState('')
  const [action, setAction] = useState('approved')
  const [comment, setComment] = useState('')
  const [items, setItems] = useState([
    '打开原始账号核对发布日期',
    '确认传播语境是否暗示近期事件',
    '补充中文官方信源',
  ])
  const [busy, setBusy] = useState(false)

  async function submit() {
    setBusy(true)
    try {
      await api.review(caseData.id, { reviewer, action, comment, check_items: items })
      await onDone()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ marginTop: 14, borderTop: '1px solid #e5e7eb', paddingTop: 14 }}>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 10 }}>人工审核（环节9）</div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
        <input value={reviewer} onChange={(e) => setReviewer(e.target.value)}
          placeholder="审核人" style={{ width: 140, padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13 }} />
        <select value={action} onChange={(e) => setAction(e.target.value)}
          style={{ padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13 }}>
          <option value="approved">通过</option>
          <option value="revised">修改后通过</option>
          <option value="returned">退回重做</option>
        </select>
      </div>
      <textarea value={comment} onChange={(e) => setComment(e.target.value)}
        placeholder="审核意见（必填项：确认信源独立性与语境）"
        style={{ width: '100%', padding: 10, border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13, marginBottom: 10, minHeight: 50 }} />
      <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 10 }}>
        人工确认点（勾选表示已核对）：
      </div>
      {items.map((it, i) => (
        <label key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 6, cursor: 'pointer' }}>
          <input type="checkbox" checked={items.includes(it)}
            onChange={() => setItems(items.includes(it) ? items.filter((x) => x !== it) : [...items, it])} />
          {it}
        </label>
      ))}
      <button onClick={submit} disabled={busy || items.length === 0}
        style={{
          marginTop: 8, padding: '10px 22px', background: '#059669', color: '#fff',
          border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer', opacity: busy ? 0.6 : 1,
        }}>{busy ? '提交中...' : '提交审核'}</button>
    </div>
  )
}
