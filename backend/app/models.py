import datetime
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from .database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(50), primary_key=True) # e.g. "platea", "poty"
    name = Column(String(100), nullable=False)
    folder_path = Column(Text, nullable=True)
    active_file_path = Column(Text, nullable=True)
    total_budget = Column(Float, default=0.0)
    cutoff_med_num = Column(Integer, default=11)
    cycle_start_day = Column(Integer, default=21)
    cycle_end_day = Column(Integer, default=20)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    wbs_items = relationship("WBSItem", back_populates="project", cascade="all, delete-orphan")
    scenarios = relationship("ReplanScenario", back_populates="project", cascade="all, delete-orphan")

class WBSItem(Base):
    __tablename__ = "wbs_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    code = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    level = Column(Integer, nullable=False, index=True)
    parent_code = Column(String(50), nullable=True, index=True)
    unit = Column(String(20), nullable=True)
    quantity = Column(Float, default=0.0)
    unit_price = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)
    accum_measured_pct = Column(Float, default=0.0)

    project = relationship("Project", back_populates="wbs_items")

class ScheduleTask(Base):
    __tablename__ = "schedule_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name = Column(String(255), nullable=False, index=True)
    duration = Column(Float, default=0.0)

class WBSLink(Base):
    __tablename__ = "wbs_task_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    wbs_code = Column(String(50), nullable=False, index=True)
    task_name = Column(String(255), nullable=False, index=True)
    duration = Column(Float, default=0.0)
    allocated_val = Column(Float, default=0.0)

class ReplanScenario(Base):
    __tablename__ = "replan_scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name = Column(String(100), nullable=False)
    cutoff_med_num = Column(Integer, default=11)
    cycle_start_day = Column(Integer, default=21)
    cycle_end_day = Column(Integer, default=20)
    total_budget = Column(Float, default=0.0)
    realizado_accum = Column(Float, default=0.0)
    saldo_replanejado = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="scenarios")
