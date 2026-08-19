"""Maps domain objects to PostgreSQL and implements repository interfaces.

Callers open :class:`~moj_projekt.persistence.unit_of_work.SqlAlchemyUnitOfWork`
for the transaction; repository methods flush and do not commit.

See docs/reference/MODULE_MAP.md.
"""
