# -*- coding: utf-8 -*-
"""数据模型：线索、核查任务（案件）、主张、证据、信源评价、报告、审核记录。"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, JSON, ForeignKey, Float
)
from sqlalchemy.orm import relationship
from .database import Base


class Clue(Base):
    """环节1：线索接收。"""
    __tablename__ = "clues"

    id = Column(Integer, primary_key=True, index=True)
    clue_no = Column(String(32), unique=True, index=True)          # CLUE-20260916-001
    title = Column(String(200), default="")
    content_type = Column(String(20), default="text")              # text / link / image / video / audio
    raw_text = Column(Text, default="")                            # 原文（文字或转写结果）
    translated_text = Column(Text, default="")                     # 中文翻译
    source_platform = Column(String(50), default="")               # 来源平台，如 X / Telegram
    source_account = Column(String(100), default="")
    source_link = Column(String(500), default="")
    published_at = Column(String(40), default="")
    media_path = Column(String(300), default="")                   # 上传媒体文件路径
    image_url = Column(String(500), default="")                    # 图片公开链接（优先用于识图）
    submitted_by = Column(String(50), default="")
    submitted_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="received")                # received -> screening -> ...

    case = relationship("Case", back_populates="clue", uselist=False)


class Case(Base):
    """核查任务（案件）：承载 9 环节状态流转。"""
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_no = Column(String(32), unique=True, index=True)          # ZT-2026-xxxx
    clue_id = Column(Integer, ForeignKey("clues.id"))
    title = Column(String(200), default="")
    status = Column(String(20), default="screening")               # screening/decomposing/searching/tracing/verifying/evaluating/reporting/reviewing/done
    stage = Column(Integer, default=1)                             # 1-9 对应环节进度
    priority = Column(String(10), default="中")
    assignee = Column(String(50), default="")
    screening_result = Column(JSON, default=dict)                  # 环节2：价值初筛结果
    keywords = Column(JSON, default=list)                          # 环节4：多语种关键词
    search_results = Column(JSON, default=list)                    # 环节4：检索结果
    trace_results = Column(JSON, default=list)                     # 环节5：出处追踪结果
    verification_results = Column(JSON, default=list)              # 环节6：交叉验证结果
    source_evals = Column(JSON, default=list)                      # 环节7：信源评价结果
    final_conclusion = Column(String(30), default="")              # 结论分类
    running_log = Column(JSON, default=list)                       # 自动流水线进度日志
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clue = relationship("Clue", back_populates="case")
    claims = relationship("Claim", back_populates="case", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")
    report = relationship("Report", back_populates="case", uselist=False)
    reviews = relationship("ReviewLog", back_populates="case", cascade="all, delete-orphan")


class Claim(Base):
    """环节3：事实主张拆解结果。"""
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    text = Column(Text, default="")
    claim_type = Column(String(20), default="fact")                # fact / view / emotion
    elements = Column(JSON, default=dict)                          # 人物/地点/时间/事件
    searchable = Column(Integer, default=1)                        # 是否可核查
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="claims")


class Evidence(Base):
    """环节6：交叉验证的证据条目。"""
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    name = Column(String(200), default="")
    source_org = Column(String(100), default="")
    source_type = Column(String(30), default="")                   # 社交媒体/新闻媒体/官方文件/国际媒体/事实核查机构/数据库
    publish_date = Column(String(40), default="")
    url = Column(String(500), default="")
    relation = Column(String(20), default="待确认")                 # 支持/反驳/背景/待确认
    reliability = Column(String(20), default="中")                  # 高/较高/中/低
    note = Column(Text, default="")
    is_independent = Column(Integer, default=1)                    # 是否独立信源（转载不计）
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="evidence")


class Report(Base):
    """环节8：核查报告（结构化）。"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), unique=True)
    preliminary_conclusion = Column(Text, default="")              # 初步结论（含判定说明）
    conclusion = Column(String(30), default="")                    # 结论分类（8类）
    confidence = Column(String(10), default="中")
    summary = Column(Text, default="")                             # 核查摘要
    evidence_table = Column(JSON, default=list)                    # 证据表（名称/来源/日期/关系/可信度/链接）
    source_links = Column(JSON, default=list)                      # 来源链接清单
    gaps = Column(JSON, default=list)                              # 证据缺口
    pending_items = Column(JSON, default=list)                     # 待确认事项
    generated_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="report")


class ReviewLog(Base):
    """环节9：人工审核记录。"""
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    reviewer = Column(String(50), default="")
    action = Column(String(20), default="")                        # approved / revised / returned
    comment = Column(Text, default="")
    check_items = Column(JSON, default=list)                       # 人工确认点清单
    reviewed_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="reviews")
