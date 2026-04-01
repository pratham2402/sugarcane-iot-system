"""Database model definitions (placeholder for SQLAlchemy migration)."""

# Currently using raw SQLite via connection.py and repository.py.
# When migrating to PostgreSQL with SQLAlchemy, define ORM models here:
#
# from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime
# from sqlalchemy.ext.declarative import declarative_base
#
# Base = declarative_base()
#
# class TelemetryReading(Base):
#     __tablename__ = "telemetry_readings"
#     id = Column(Integer, primary_key=True)
#     node_id = Column(String, nullable=False)
#     timestamp = Column(Integer, nullable=False)
#     ...
