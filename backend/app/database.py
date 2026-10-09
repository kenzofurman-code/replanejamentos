"""
PostgreSQL & SQLite Database layer for Replanejamento Físico-Financeiro.
Provides relational persistence with JSON serialization for complex tree/schedule structures.
"""
import os
import json
import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback to local SQLite if DATABASE_URL is not configured
    db_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "replanejamento.db").replace("\\", "/")
    DATABASE_URL = f"sqlite:///{db_path}"

# Handle postgres:// vs postgresql:// for SQLAlchemy using psycopg2 driver
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=10 if not DATABASE_URL.startswith("sqlite") else 5,
    max_overflow=20 if not DATABASE_URL.startswith("sqlite") else 10
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class ProjectModel(Base):
    __tablename__ = "projects"

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    total_budget = Column(Float, default=0.0)
    start_date = Column(String(50), nullable=True)
    end_date = Column(String(50), nullable=True)
    cutoff_date = Column(String(50), nullable=True)
    cutoff_med_num = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class BudgetItemModel(Base):
    __tablename__ = "budget_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(100), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    unit = Column(String(50), nullable=True)
    quantity = Column(Float, default=0.0)
    unit_price = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)
    weight = Column(Float, default=0.0)
    level = Column(Integer, default=1)
    parent_code = Column(String(100), nullable=True)
    accum_measured_pct = Column(Float, default=0.0)

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_project_budget_item"),
        Index("ix_budget_project_code", "project_id", "code"),
    )


class ScheduleTaskModel(Base):
    __tablename__ = "schedule_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(100), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_key = Column(String(255), nullable=False)
    task_id = Column(String(100), nullable=False)
    name = Column(Text, nullable=False)
    duration = Column(Float, default=0.0)
    start_date = Column(String(50), nullable=True)
    end_date = Column(String(50), nullable=True)
    is_summary = Column(Boolean, default=False)
    predecessors_json = Column(Text, default="[]")
    successors_json = Column(Text, default="[]")
    tower = Column(String(100), nullable=True)
    floor = Column(String(100), nullable=True)
    daily_json = Column(Text, default="{}")

    __table_args__ = (
        UniqueConstraint("project_id", "task_key", name="uq_project_task_key"),
        Index("ix_task_project_task_id", "project_id", "task_id"),
    )


class EAPScheduleLinkModel(Base):
    __tablename__ = "eap_schedule_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(100), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    l5_code = Column(String(100), nullable=False, index=True)
    task_id = Column(String(100), nullable=True)
    task_name = Column(Text, nullable=True)
    weight = Column(Float, default=1.0)
    link_data_json = Column(Text, default="{}")


class MeasurementHistoryModel(Base):
    __tablename__ = "measurement_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(100), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    med_num = Column(Integer, nullable=False)
    date = Column(String(50), nullable=True)
    label = Column(String(100), nullable=True)
    planned_pct = Column(Float, default=0.0)
    measured_pct = Column(Float, default=0.0)
    value = Column(Float, default=0.0)

    __table_args__ = (
        UniqueConstraint("project_id", "med_num", name="uq_project_med_history"),
    )


class MeasurementItemModel(Base):
    __tablename__ = "measurement_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(100), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(100), nullable=False, index=True)
    monthly_json = Column(Text, default="{}")

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_project_item_monthly"),
    )


class DomainVersionModel(Base):
    __tablename__ = "domain_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(100), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String(50), nullable=False)  # orcamento, cronograma, distribuicao, medicao
    active_version_id = Column(String(100), default="atual")
    versions_json = Column(Text, default="[]")

    __table_args__ = (
        UniqueConstraint("project_id", "domain", name="uq_project_domain_version"),
    )


class VersionEditsModel(Base):
    __tablename__ = "version_edits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(100), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String(50), nullable=False)
    version_id = Column(String(100), default="atual")
    edits_json = Column(Text, default="{}")
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    __table_args__ = (
        UniqueConstraint("project_id", "domain", "version_id", name="uq_project_domain_version_edits"),
    )


def init_db():
    """Creates all database tables."""
    Base.metadata.create_all(bind=engine)


def save_project_to_db(project_id: str, parsed: Dict[str, Any]):
    """
    Saves full project tree, schedule tasks, links and measurements to the database.
    """
    init_db()
    session = SessionLocal()
    try:
        # 1. Project Header
        proj = session.query(ProjectModel).filter_by(id=project_id).first()
        if not proj:
            proj = ProjectModel(id=project_id)
            session.add(proj)

        proj.name = str(parsed.get("project_name") or project_id)
        proj.total_budget = float(parsed.get("total_budget") or 0.0)
        proj.start_date = str(parsed.get("start_date") or "")
        proj.end_date = str(parsed.get("end_date") or "")
        proj.cutoff_date = str(parsed.get("cutoff_date") or "")
        proj.cutoff_med_num = int(parsed.get("cutoff_med_num") or 0)
        proj.updated_at = _now()
        session.flush()

        # 2. Budget Items
        session.query(BudgetItemModel).filter_by(project_id=project_id).delete()
        b_items = []
        for code, item in parsed.get("budget_items", {}).items():
            b_items.append(BudgetItemModel(
                project_id=project_id,
                code=code,
                description=item.get("description"),
                unit=item.get("unit"),
                quantity=float(item.get("quantity") or 0.0),
                unit_price=float(item.get("unit_price") or 0.0),
                total_price=float(item.get("total_price") or 0.0),
                weight=float(item.get("weight") or 0.0),
                level=int(item.get("level") or 1),
                parent_code=item.get("parent_code"),
                accum_measured_pct=float(item.get("accum_measured_pct") or 0.0)
            ))
        if b_items:
            session.bulk_save_objects(b_items)

        # 3. Schedule Tasks
        session.query(ScheduleTaskModel).filter_by(project_id=project_id).delete()
        s_tasks = []
        for t_k, t_data in parsed.get("tasks", {}).items():
            t_id = str(t_data.get("id") or t_k)
            # convert daily keys to string dates for JSON
            daily_str = {}
            for dt, val in t_data.get("daily", {}).items():
                k_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)
                daily_str[k_str] = float(val)

            s_tasks.append(ScheduleTaskModel(
                project_id=project_id,
                task_key=t_k,
                task_id=t_id,
                name=t_data.get("name") or t_k,
                duration=float(t_data.get("duration") or 0.0),
                start_date=str(t_data.get("start") or ""),
                end_date=str(t_data.get("finish") or ""),
                is_summary=bool(t_data.get("is_summary")),
                predecessors_json=json.dumps(t_data.get("predecessors") or []),
                successors_json=json.dumps(t_data.get("successors") or []),
                tower=t_data.get("tower"),
                floor=t_data.get("floor"),
                daily_json=json.dumps(daily_str)
            ))
        if s_tasks:
            session.bulk_save_objects(s_tasks)

        # 4. Links
        session.query(EAPScheduleLinkModel).filter_by(project_id=project_id).delete()
        links = []
        for item in parsed.get("all_links", []):
            code = item.get("l5_code") or item.get("wbs_code") or ""
            t_id = str(item.get("task_id") or item.get("id") or "") if (item.get("task_id") is not None or item.get("id") is not None) else None
            t_name = item.get("task_name") or item.get("name") or ""
            wt = float(item.get("weight") if item.get("weight") is not None else (item.get("allocated_val") or 1.0))
            links.append(EAPScheduleLinkModel(
                project_id=project_id,
                l5_code=code,
                task_id=t_id,
                task_name=t_name,
                weight=wt,
                link_data_json=json.dumps(item)
            ))
        if links:
            session.bulk_save_objects(links)

        # 5. Measurement History
        session.query(MeasurementHistoryModel).filter_by(project_id=project_id).delete()
        m_hist = []
        for h in parsed.get("history_monthly", []):
            m_hist.append(MeasurementHistoryModel(
                project_id=project_id,
                med_num=int(h.get("med_num") or 0),
                date=str(h.get("date") or ""),
                label=h.get("label"),
                planned_pct=float(h.get("planned_pct") or 0.0),
                measured_pct=float(h.get("measured_pct") or 0.0),
                value=float(h.get("value") or 0.0)
            ))
        if m_hist:
            session.bulk_save_objects(m_hist)

        # 6. Measurement Items Monthly
        session.query(MeasurementItemModel).filter_by(project_id=project_id).delete()
        m_items = []
        for code, m_dict in parsed.get("item_monthly_measurements", {}).items():
            m_items.append(MeasurementItemModel(
                project_id=project_id,
                code=code,
                monthly_json=json.dumps(m_dict)
            ))
        if m_items:
            session.bulk_save_objects(m_items)

        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def load_project_from_db(project_id: str) -> Optional[Dict[str, Any]]:
    """
    Loads project from database and reconstructs the standard parsed dictionary.
    Returns None if project not found in database.
    """
    init_db()
    session = SessionLocal()
    try:
        proj = session.query(ProjectModel).filter_by(id=project_id).first()
        if not proj:
            return None

        # 1. Budget items
        b_records = session.query(BudgetItemModel).filter_by(project_id=project_id).all()
        budget_items = {}
        item_measurements = {}
        for r in b_records:
            budget_items[r.code] = {
                "code": r.code,
                "description": r.description,
                "unit": r.unit,
                "quantity": r.quantity,
                "unit_price": r.unit_price,
                "total_price": r.total_price,
                "weight": r.weight,
                "level": r.level,
                "parent_code": r.parent_code,
                "accum_measured_pct": r.accum_measured_pct
            }
            if r.accum_measured_pct:
                item_measurements[r.code] = r.accum_measured_pct

        # 2. Schedule tasks
        t_records = session.query(ScheduleTaskModel).filter_by(project_id=project_id).all()
        tasks = {}
        for r in t_records:
            daily_dict = {}
            try:
                raw_daily = json.loads(r.daily_json or "{}")
                for k_str, val in raw_daily.items():
                    d = datetime.date.fromisoformat(k_str)
                    daily_dict[d] = float(val)
            except Exception:
                pass

            preds = []
            try:
                preds = json.loads(r.predecessors_json or "[]")
            except Exception:
                pass

            succs = []
            try:
                succs = json.loads(r.successors_json or "[]")
            except Exception:
                pass

            t_obj = {
                "id": r.task_id,
                "name": r.name,
                "duration": r.duration,
                "start": r.start_date,
                "finish": r.end_date,
                "is_summary": r.is_summary,
                "predecessors": preds,
                "successors": succs,
                "tower": r.tower,
                "floor": r.floor,
                "daily": daily_dict
            }
            tasks[r.task_key] = t_obj

        # 3. Links
        l_records = session.query(EAPScheduleLinkModel).filter_by(project_id=project_id).all()
        links_by_l5 = {}
        all_links = []
        for r in l_records:
            entry = {}
            if r.link_data_json:
                try:
                    entry = json.loads(r.link_data_json)
                except Exception:
                    pass
            if not entry:
                entry = {
                    "l5_code": r.l5_code,
                    "wbs_code": r.l5_code,
                    "task_id": r.task_id,
                    "task_name": r.task_name,
                    "weight": r.weight
                }
            all_links.append(entry)
            code_k = entry.get("l5_code") or entry.get("wbs_code") or r.l5_code
            links_by_l5.setdefault(code_k, []).append(entry)

        # 4. History
        h_records = session.query(MeasurementHistoryModel).filter_by(project_id=project_id).order_by(MeasurementHistoryModel.med_num).all()
        history_monthly = []
        for r in h_records:
            history_monthly.append({
                "med_num": r.med_num,
                "date": r.date,
                "label": r.label,
                "planned_pct": r.planned_pct,
                "measured_pct": r.measured_pct,
                "value": r.value
            })

        # 5. Monthly item measurements
        m_records = session.query(MeasurementItemModel).filter_by(project_id=project_id).all()
        item_monthly_measurements = {}
        for r in m_records:
            try:
                raw_m = json.loads(r.monthly_json or "{}")
                # keys might be strings, convert med_num to int
                m_parsed = {}
                for k, v in raw_m.items():
                    m_parsed[int(k) if k.isdigit() else k] = v
                item_monthly_measurements[r.code] = m_parsed
            except Exception:
                pass

        # Parse start_date / end_date
        s_date = None
        if proj.start_date:
            try:
                s_date = datetime.date.fromisoformat(proj.start_date[:10])
            except Exception:
                pass

        e_date = None
        if proj.end_date:
            try:
                e_date = datetime.date.fromisoformat(proj.end_date[:10])
            except Exception:
                pass

        c_date = None
        if proj.cutoff_date:
            try:
                c_date = datetime.date.fromisoformat(proj.cutoff_date[:10])
            except Exception:
                pass

        return {
            "project_name": proj.name,
            "total_budget": proj.total_budget,
            "start_date": s_date,
            "end_date": e_date,
            "cutoff_med_num": proj.cutoff_med_num,
            "cutoff_date": c_date,
            "budget_items": budget_items,
            "tasks": tasks,
            "links_by_l5": links_by_l5,
            "all_links": all_links,
            "item_measurements": item_measurements,
            "item_monthly_measurements": item_monthly_measurements,
            "history_monthly": history_monthly
        }
    finally:
        session.close()


def save_domain_edits_db(project_id: str, domain: str, version_id: str, edits: Dict[str, Any]):
    """Saves active overrides (schedule overrides, custom links, custom medicao) into database."""
    init_db()
    session = SessionLocal()
    try:
        vid = version_id or "atual"
        record = session.query(VersionEditsModel).filter_by(
            project_id=project_id, domain=domain, version_id=vid
        ).first()

        if not edits:
            if record:
                session.delete(record)
                session.commit()
            return

        if not record:
            record = VersionEditsModel(
                project_id=project_id,
                domain=domain,
                version_id=vid
            )
            session.add(record)

        record.edits_json = json.dumps(edits, ensure_ascii=False)
        record.updated_at = _now()
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_domain_edits_db(project_id: str, domain: str, version_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves overrides from database."""
    init_db()
    session = SessionLocal()
    try:
        vid = version_id or "atual"
        record = session.query(VersionEditsModel).filter_by(
            project_id=project_id, domain=domain, version_id=vid
        ).first()
        if record and record.edits_json:
            return json.loads(record.edits_json)
        return {}
    finally:
        session.close()


def save_curvas_config_db(project_id: str, configs: Dict[str, Any]):
    """Saves curvas stage parameters in the database."""
    init_db()
    session = SessionLocal()
    try:
        record = session.query(VersionEditsModel).filter_by(
            project_id=project_id, domain="curvas_config", version_id="atual"
        ).first()
        if not record:
            record = VersionEditsModel(
                project_id=project_id,
                domain="curvas_config",
                version_id="atual"
            )
            session.add(record)
        record.edits_json = json.dumps(configs, ensure_ascii=False)
        record.updated_at = _now()
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_curvas_config_db(project_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves curvas stage parameters from the database."""
    init_db()
    session = SessionLocal()
    try:
        record = session.query(VersionEditsModel).filter_by(
            project_id=project_id, domain="curvas_config", version_id="atual"
        ).first()
        if record and record.edits_json:
            return json.loads(record.edits_json)
        return None
    finally:
        session.close()

