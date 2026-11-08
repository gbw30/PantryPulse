"""net_batches is LIST-partitioned by dataset version, like the history tables (W2-06, Gabriel
2026-11-08).

At the envelope maximum the import publish held the queue lock 4.5 s, 3.5 s of it in
`INSERT INTO net_batches SELECT * FROM <staged>` (row-by-row FK checks; W0-08 §7). The import job
now builds each version's batches partition outside the lock and publish ATTACHes it.

A partitioned table's keys must include the partition key: the primary key becomes
(dataset_version_id, id), and UNIQUE (organization_id, id) is dropped (no foreign key references a
batch). Batch rows become immutable (`ppv1_immutable`), like their dataset version.

Upgrade and downgrade copy every row, `recorded_at` included, into the rebuilt table.
"""

import sqlalchemy as sa
from alembic import op

revision = "ppv1_0013"
down_revision = "ppv1_0012"
branch_labels = None
depends_on = None

COLUMNS = ("id, organization_id, dataset_version_id, location_id, product_id, external_id, "
           "quantity, expiry_date, non_expiring, received_date, recorded_at")
# ppv1_0008's DDL with the primary key, tenant key and partitioning filled in.
TABLE = """CREATE TABLE net_batches (
	dataset_version_id UUID NOT NULL,
	location_id UUID NOT NULL,
	product_id UUID NOT NULL,
	external_id TEXT NOT NULL,
	quantity BIGINT NOT NULL,
	expiry_date DATE,
	non_expiring BOOLEAN NOT NULL,
	received_date DATE,
	organization_id UUID NOT NULL,
	id UUID NOT NULL,
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
	CONSTRAINT pk_net_batches PRIMARY KEY ({primary_key}),
	CONSTRAINT fk_net_batches_organization_id_dataset_version_id_datas_5365 FOREIGN KEY(organization_id, dataset_version_id) REFERENCES dataset_versions (organization_id, id) ON DELETE RESTRICT,
	CONSTRAINT fk_net_batches_organization_id_dataset_version_id_locat_656c FOREIGN KEY(organization_id, dataset_version_id, location_id) REFERENCES net_locations (organization_id, dataset_version_id, id) ON DELETE RESTRICT,
	CONSTRAINT fk_net_batches_organization_id_dataset_version_id_produ_72d8 FOREIGN KEY(organization_id, dataset_version_id, product_id) REFERENCES net_products (organization_id, dataset_version_id, id) ON DELETE RESTRICT,
	CONSTRAINT uq_net_batches_dataset_version_id_location_id_product_i_50f2 UNIQUE (dataset_version_id, location_id, product_id, external_id),
	CONSTRAINT ck_net_batches_quantity CHECK (quantity >= 0),
	CONSTRAINT ck_net_batches_expiry_xor_non_expiring CHECK ((expiry_date IS NOT NULL AND NOT non_expiring) OR (expiry_date IS NULL AND non_expiring)),
	CONSTRAINT fk_net_batches_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT{tenant_key}
){partition_by}"""  # noqa: E501
INDEXED = ("pk_net_batches", "uq_net_batches_dataset_version_id_location_id_product_i_50f2",
           "uq_net_batches_organization_id_id")


def _rebuild(ddl):
    """Move the rows into a new net_batches built by `ddl`; returns the old table's name."""
    op.execute("ALTER TABLE net_batches RENAME TO net_batches_previous")
    for name in INDEXED:  # index names are schema-wide: free them for the new table
        op.execute(f"ALTER TABLE net_batches_previous DROP CONSTRAINT IF EXISTS {name}")
    op.execute(ddl)
    return "net_batches_previous"


def upgrade():
    old = _rebuild(TABLE.format(primary_key="dataset_version_id, id", tenant_key="",
                                partition_by=" PARTITION BY LIST (dataset_version_id)"))
    versions = op.get_bind().scalars(sa.text(f"SELECT DISTINCT dataset_version_id FROM {old}"))
    for version in versions.all():
        op.execute(f"CREATE TABLE net_batches_{version.hex} PARTITION OF net_batches "
                   f"FOR VALUES IN ('{version}')")
    op.execute(f"INSERT INTO net_batches ({COLUMNS}) SELECT {COLUMNS} FROM {old}")
    op.execute(f"DROP TABLE {old}")
    op.execute("CREATE TRIGGER ppv1_immutable BEFORE UPDATE OR DELETE ON net_batches "
               "FOR EACH ROW EXECUTE FUNCTION ppv1_immutable()")


def downgrade():
    """Fails cleanly (UniqueViolation on pk_net_batches) if two versions hold the same batch id:
    only direct SQL can do that, since imports give every batch a new uuid4."""
    tenant_key = ",\n\tCONSTRAINT uq_net_batches_organization_id_id UNIQUE (organization_id, id)"
    old = _rebuild(TABLE.format(primary_key="id", tenant_key=tenant_key, partition_by=""))
    op.execute(f"INSERT INTO net_batches ({COLUMNS}) SELECT {COLUMNS} FROM {old}")
    op.execute(f"DROP TABLE {old}")  # and its partitions and trigger
