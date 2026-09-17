# -*- coding: utf-8 -*-
"""初始化演示数据：用真实验证过的"美日加军演"案例，跑通全部 9 环节。

用法：python -m app.seed_demo
（在 backend 目录下执行）
"""
import asyncio
from datetime import datetime

from .database import Base, engine, SessionLocal
from . import models
from .services import pipeline


DEMO_CLUE = {
    "title": "微信群流传：美日加3国军演，航母战机全出动，中国要怕了",
    "content_type": "text",
    "raw_text": (
        "Massive joint military exercise by US, Japan and Canada. "
        "Aircraft carriers and warplanes all deployed. China should be afraid."
    ),
    "translated_text": "美日加三国举行大规模联合军演，航母战机全部出动，中国要怕了。",
    "source_platform": "微信",
    "source_account": "@GlobalNewsNow",
    "source_link": "https://www.setn.com/news/838028",
    "published_at": "2020-10-27",
    "submitted_by": "李同学",
}


async def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 若已有演示数据则跳过创建
        existing = db.query(models.Clue).filter_by(title=DEMO_CLUE["title"]).first()
        if existing:
            print("演示数据已存在，跳过创建。")
            case = db.query(models.Case).filter_by(clue_id=existing.id).first()
        else:
            clue_no = f"CLUE-{datetime.now().strftime('%Y%m%d')}-001"
            clue = models.Clue(clue_no=clue_no, status="received", **DEMO_CLUE)
            db.add(clue)
            db.flush()
            case_no = f"ZT-{datetime.now().strftime('%Y')}-0001"
            case = models.Case(
                case_no=case_no, clue_id=clue.id, title=DEMO_CLUE["title"],
                status="received", stage=1, assignee="李同学",
            )
            db.add(case)
            db.commit()
            db.refresh(clue)
            db.refresh(case)
            print(f"已创建演示线索 {clue.clue_no} 与案件 {case.case_no}")

        # 逐环节跑通
        print("\n===== 跑通 9 环节 =====")
        clue = db.query(models.Clue).filter_by(id=case.clue_id).first()

        print(f"\n[环节2] 价值初筛")
        r = pipeline.run_screening(case, clue)
        print(f"  通过: {r['passed']} | 得分: {r['score']} | {r['reason']}")

        print(f"\n[环节3] 主张拆解")
        r = pipeline.run_decompose(case, clue, db)
        for c in r["claims"]:
            print(f"  [{c['type']}] {c['text'][:50]} | 要素: {c.get('elements', {})}")
        print(f"  关键词: 中={r['keywords'].get('zh')} 英={r['keywords'].get('en')}")

        print(f"\n[环节4] 多语种检索")
        r = await pipeline.run_search(case)
        for s in r["results"][:4]:
            print(f"  - {s['title'][:40]} | {s['source']} | {s['date']}")

        print(f"\n[环节5] 出处追踪")
        r = await pipeline.run_trace(case, clue)
        for t in r["results"]:
            print(f"  - {t['matched_title'][:40]} | {t['matched_site']} | {t['published_date']}")
        if r.get("mode") == "demo":
            print(f"  [提示] {r.get('warning', '')}")

        print(f"\n[环节6] 交叉验证")
        r = pipeline.run_verify(case, db)
        print(f"  主张数: {r['claim_count']} | 证据数: {r['evidence_count']} | 独立来源: {r['independent_count']}")
        print(f"  提示: {r['warning']}")

        print(f"\n[环节7] 信源评价")
        evals = pipeline.run_evaluate(case)
        for e in evals[:4]:
            print(f"  - {e['name'][:30]} | 评级: {e.get('grade')} | {e.get('reason', '')[:30]}")

        print(f"\n[环节8] 报告生成")
        r = pipeline.run_report(case, db)
        print(f"  结论: {r['conclusion']} | 置信度: {r['confidence']}")
        print(f"  摘要: {r['summary'][:80]}")

        print(f"\n[环节9] 人工审核")
        check_items = [
            "打开原始账号核对发布日期",
            "确认传播语境是否暗示近期事件",
            "补充中文官方信源",
        ]
        r = pipeline.run_review(case, db, reviewer="张老师", action="approved",
                                comment="核心事实属实，需在报告中标注旧闻语境。",
                                check_items=check_items)
        print(f"  审核完成，案件状态: {r['case_status']}")

        print("\n===== 9 环节跑通完成 =====")
        print(f"案件编号: {case.case_no} | 最终结论: {case.final_conclusion}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
