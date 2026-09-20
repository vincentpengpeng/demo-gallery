import React, { useEffect, useState } from 'react'

// 演示用户数据（首次加载写入 localStorage，之后增删改保存在本地）
const DEFAULT_USERS = [
  { id: 1, name: '张明', account: 'zhangming', role: '管理员', dept: '真探工作室', email: 'zhangming@zhentan.cn', phone: '138****1234', status: '启用', lastActive: '2026-09-20 09:12', note: '工作室负责人' },
  { id: 2, name: '李华', account: 'lihua', role: '核查员', dept: '分析组', email: 'lihua@zhentan.cn', phone: '139****5678', status: '启用', lastActive: '2026-09-20 08:45', note: '一线核查' },
  { id: 3, name: '王芳', account: 'wangfang', role: '核查员', dept: '分析组', email: 'wangfang@zhentan.cn', phone: '137****9012', status: '启用', lastActive: '2026-09-19 17:30', note: '涉华舆情' },
  { id: 4, name: '赵强', account: 'zhaoqiang', role: '审核员', dept: '审核组', email: 'zhaoqiang@zhentan.cn', phone: '136****3456', status: '启用', lastActive: '2026-09-19 16:05', note: '终审定论' },
  { id: 5, name: '陈静', account: 'chenjing', role: '核查员', dept: '分析组', email: 'chenjing@zhentan.cn', phone: '135****7890', status: '停用', lastActive: '2026-09-10 11:20', note: '休假中' },
  { id: 6, name: '刘洋', account: 'liuyang', role: '审核员', dept: '审核组', email: 'liuyang@zhentan.cn', phone: '134****2345', status: '启用', lastActive: '2026-09-18 14:40', note: '负责重大案例复核' },
]

const ROLE_COLORS = {
  '管理员': { color: '#dc2626', bg: '#fef2f2' },
  '审核员': { color: '#d97706', bg: '#fef3c7' },
  '核查员': { color: '#2563eb', bg: '#eff6ff' },
}

const STORAGE_KEY = 'zhentan_users'

function loadUsers() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch (e) { /* ignore */ }
  return DEFAULT_USERS
}

export default function UserManagement() {
  const [users, setUsers] = useState(loadUsers)
  const [filterRole, setFilterRole] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [keyword, setKeyword] = useState('')
  const [modal, setModal] = useState(null)   // null / 'add' / user(编辑)
  const [viewing, setViewing] = useState(null) // 查看详情
  const [form, setForm] = useState({ name: '', account: '', role: '核查员', dept: '', email: '', phone: '', status: '启用', note: '' })
  const [saveMsg, setSaveMsg] = useState('')

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(users)) } catch (e) { /* ignore */ }
  }, [users])

  const roles = ['管理员', '审核员', '核查员']
  const statuses = ['启用', '停用']

  let list = users
  if (filterRole !== 'all') list = list.filter((u) => u.role === filterRole)
  if (filterStatus !== 'all') list = list.filter((u) => u.status === filterStatus)
  if (keyword) list = list.filter((u) => (u.name + u.account + u.dept + u.email).toLowerCase().includes(keyword.toLowerCase()))

  const openAdd = () => {
    setForm({ name: '', account: '', role: '核查员', dept: '分析组', email: '', phone: '', status: '启用', note: '' })
    setModal('add')
  }
  const openEdit = (u) => {
    setForm({ ...u })
    setModal(u)
  }
  const openView = (u) => setViewing(u)

  const saveUser = () => {
    if (!form.name.trim() || !form.account.trim()) {
      setSaveMsg('姓名和账号不能为空')
      return
    }
    if (modal === 'add') {
      if (users.some((u) => u.account === form.account.trim())) {
        setSaveMsg('账号已存在，请更换')
        return
      }
      const newUser = { ...form, id: Date.now(), name: form.name.trim(), account: form.account.trim(), lastActive: '—' }
      setUsers([newUser, ...users])
    } else {
      setUsers(users.map((u) => (u.id === modal.id ? { ...u, ...form, name: form.name.trim(), account: form.account.trim() } : u)))
    }
    setModal(null)
    setSaveMsg('')
  }

  const toggleStatus = (u) => {
    setUsers(users.map((x) => (x.id === u.id ? { ...x, status: x.status === '启用' ? '停用' : '启用' } : x)))
  }

  const deleteUser = (u) => {
    if (!window.confirm(`确定删除用户「${u.name}（${u.account}）」？`)) return
    setUsers(users.filter((x) => x.id !== u.id))
  }

  const resetDemo = () => {
    if (!window.confirm('恢复为默认演示数据？当前修改会丢失。')) return
    setUsers(DEFAULT_USERS)
    try { localStorage.removeItem(STORAGE_KEY) } catch (e) { /* ignore */ }
  }

  const inputStyle = {
    width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db',
    fontSize: 13, boxSizing: 'border-box', marginBottom: 10,
  }

  return (
    <div>
      {/* 顶部 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <h2 style={{ fontSize: 20, marginBottom: 4 }}>用户管理</h2>
          <p style={{ color: '#6b7280', fontSize: 13 }}>
            系统用户与权限管理，支持成员协作与操作留痕
            <span style={{ color: '#d97706', marginLeft: 8 }}>（共 {users.length} 人）</span>
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={resetDemo} style={{ padding: '8px 14px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: '1px solid #d1d5db', background: '#fff', color: '#6b7280' }}>
            恢复默认
          </button>
          <button onClick={openAdd} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: 'none', background: '#2563eb', color: '#fff' }}>
            + 新增用户
          </button>
        </div>
      </div>

      {/* 筛选栏 */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={filterRole} onChange={(e) => setFilterRole(e.target.value)}
          style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13 }}>
          <option value="all">全部角色</option>
          {roles.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}
          style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13 }}>
          <option value="all">全部状态</option>
          {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索姓名 / 账号 / 部门 / 邮箱…"
          style={{ padding: '7px 14px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: 13, width: 260, marginLeft: 'auto' }}
        />
      </div>

      {/* 用户表格 */}
      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#f9fafb', color: '#6b7280', textAlign: 'left' }}>
              <th style={{ padding: '12px 16px' }}>姓名</th>
              <th style={{ padding: '12px 16px' }}>账号</th>
              <th style={{ padding: '12px 16px' }}>角色</th>
              <th style={{ padding: '12px 16px' }}>部门</th>
              <th style={{ padding: '12px 16px' }}>邮箱</th>
              <th style={{ padding: '12px 16px' }}>状态</th>
              <th style={{ padding: '12px 16px' }}>最近活跃</th>
              <th style={{ padding: '12px 16px' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {list.map((u) => {
              const rc = ROLE_COLORS[u.role] || { color: '#6b7280', bg: '#f3f4f6' }
              return (
                <tr key={u.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ cursor: 'pointer', color: '#2563eb', fontWeight: 500 }} onClick={() => openView(u)}>{u.name}</span>
                    {u.note && <span style={{ fontSize: 11, color: '#9ca3af', marginLeft: 6 }}>（{u.note}）</span>}
                  </td>
                  <td style={{ padding: '10px 16px', color: '#6b7280' }}>@{u.account}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ padding: '2px 10px', borderRadius: 10, fontSize: 12, background: rc.bg, color: rc.color }}>{u.role}</span>
                  </td>
                  <td style={{ padding: '10px 16px' }}>{u.dept}</td>
                  <td style={{ padding: '10px 16px', color: '#6b7280' }}>{u.email}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ padding: '2px 10px', borderRadius: 10, fontSize: 12, background: u.status === '启用' ? '#ecfdf5' : '#f3f4f6', color: u.status === '启用' ? '#059669' : '#6b7280' }}>{u.status}</span>
                  </td>
                  <td style={{ padding: '10px 16px', color: '#9ca3af', fontSize: 12 }}>{u.lastActive}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={() => openEdit(u)} style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', border: '1px solid #d1d5db', background: '#fff', color: '#374151' }}>编辑</button>
                      <button onClick={() => toggleStatus(u)} style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', border: '1px solid #d1d5db', background: '#fff', color: u.status === '启用' ? '#d97706' : '#059669' }}>
                        {u.status === '启用' ? '停用' : '启用'}
                      </button>
                      <button onClick={() => deleteUser(u)} style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer', border: '1px solid #fecaca', background: '#fef2f2', color: '#dc2626' }}>删除</button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {list.length === 0 && <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: '#9ca3af' }}>暂无匹配用户</td></tr>}
          </tbody>
        </table>
      </div>

      {/* 查看详情弹窗 */}
      {viewing && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }} onClick={() => setViewing(null)}>
          <div style={{ background: '#fff', borderRadius: 14, padding: 24, maxWidth: 480, width: '90%', boxShadow: '0 20px 50px rgba(0,0,0,0.25)' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div style={{ fontSize: 17, fontWeight: 700 }}>{viewing.name}</div>
              <button onClick={() => setViewing(null)} style={{ border: 'none', background: 'none', fontSize: 18, cursor: 'pointer', color: '#9ca3af' }}>×</button>
            </div>
            {[
              ['账号', `@${viewing.account}`],
              ['角色', viewing.role],
              ['部门', viewing.dept],
              ['邮箱', viewing.email],
              ['电话', viewing.phone || '—'],
              ['状态', viewing.status],
              ['最近活跃', viewing.lastActive],
              ['备注', viewing.note || '—'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', marginBottom: 10 }}>
                <span style={{ width: 90, color: '#6b7280', fontSize: 13 }}>{k}</span>
                <span style={{ fontSize: 13, color: '#374151' }}>{v}</span>
              </div>
            ))}
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
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
              {modal === 'add' ? '新增用户' : `编辑用户：${modal.name}`}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 14px' }}>
              <div>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>姓名 *</div>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="姓名" style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>账号 *</div>
                <input value={form.account} onChange={(e) => setForm({ ...form, account: e.target.value })} placeholder="登录账号" style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>角色</div>
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} style={{ ...inputStyle, width: '100%' }}>
                  {roles.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>部门</div>
                <input value={form.dept} onChange={(e) => setForm({ ...form, dept: e.target.value })} placeholder="所属部门" style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>邮箱</div>
                <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="邮箱" style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>电话</div>
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="电话" style={inputStyle} />
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>状态</div>
                <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} style={{ ...inputStyle, width: '100%' }}>
                  {statuses.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>备注</div>
                <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="备注" style={inputStyle} />
              </div>
            </div>
            {saveMsg && <div style={{ fontSize: 12, color: '#dc2626', marginBottom: 8 }}>{saveMsg}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 6 }}>
              <button onClick={() => setModal(null)} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: '1px solid #d1d5db', background: '#fff', color: '#374151' }}>取消</button>
              <button onClick={saveUser} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, cursor: 'pointer', border: 'none', background: '#2563eb', color: '#fff' }}>
                {modal === 'add' ? '保存' : '保存修改'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
