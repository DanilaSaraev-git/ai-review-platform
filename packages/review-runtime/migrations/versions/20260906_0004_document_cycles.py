"""Add logical document families and independent mutable review-cycle snapshots.

Revision ID: 20260906_0004
Revises: 20260906_0003
"""
from alembic import op

revision = "20260906_0004"
down_revision = "20260906_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE document_families (
        organization_id varchar(36) NOT NULL, workspace_id varchar(36) NOT NULL,
        id varchar(36) NOT NULL, name varchar(255) NOT NULL, created_by varchar(36) NOT NULL,
        created_at timestamptz NOT NULL,
        PRIMARY KEY(organization_id,workspace_id,id),
        FOREIGN KEY(organization_id,workspace_id,created_by) REFERENCES actors(organization_id,workspace_id,id)
      );
      CREATE TABLE document_family_versions (
        organization_id varchar(36) NOT NULL, workspace_id varchar(36) NOT NULL,
        document_id varchar(36) NOT NULL, family_id varchar(36) NOT NULL,
        version_number integer NOT NULL CHECK(version_number > 0), unchanged_from_previous boolean NOT NULL,
        PRIMARY KEY(organization_id,workspace_id,document_id),
        UNIQUE(organization_id,workspace_id,family_id,version_number),
        FOREIGN KEY(organization_id,workspace_id,document_id) REFERENCES document_versions(organization_id,workspace_id,id),
        FOREIGN KEY(organization_id,workspace_id,family_id) REFERENCES document_families(organization_id,workspace_id,id)
      );
      CREATE TABLE review_cycles (
        organization_id varchar(36) NOT NULL, workspace_id varchar(36) NOT NULL,
        run_id varchar(36) NOT NULL, family_id varchar(36) NOT NULL,
        baseline_run_id varchar(36), revision integer NOT NULL DEFAULT 0,
        value json NOT NULL, lineage json NOT NULL, previous json NOT NULL,
        PRIMARY KEY(organization_id,workspace_id,run_id),
        FOREIGN KEY(organization_id,workspace_id,run_id) REFERENCES review_runs(organization_id,workspace_id,id),
        FOREIGN KEY(organization_id,workspace_id,baseline_run_id) REFERENCES review_runs(organization_id,workspace_id,id),
        FOREIGN KEY(organization_id,workspace_id,family_id) REFERENCES document_families(organization_id,workspace_id,id)
      );
      CREATE TABLE review_cycle_events (
        organization_id varchar(36) NOT NULL, workspace_id varchar(36) NOT NULL,
        id varchar(36) NOT NULL, run_id varchar(36) NOT NULL,
        actor_id varchar(36) NOT NULL, created_at timestamptz NOT NULL, value json NOT NULL,
        PRIMARY KEY(organization_id,workspace_id,id),
        FOREIGN KEY(organization_id,workspace_id,run_id) REFERENCES review_cycles(organization_id,workspace_id,run_id),
        FOREIGN KEY(organization_id,workspace_id,actor_id) REFERENCES actors(organization_id,workspace_id,id)
      );
      INSERT INTO document_families(organization_id,workspace_id,id,name,created_by,created_at)
        SELECT organization_id,workspace_id,id,filename,created_by,created_at FROM document_versions;
      INSERT INTO document_family_versions(organization_id,workspace_id,document_id,family_id,version_number,unchanged_from_previous)
        SELECT organization_id,workspace_id,id,id,1,false FROM document_versions;
      INSERT INTO review_cycles(organization_id,workspace_id,run_id,family_id,baseline_run_id,revision,value,lineage,previous)
        SELECT r.organization_id,r.workspace_id,r.id,m.family_id,NULL,0,
          json_build_object('run_id',r.id,'family_id',m.family_id,'document_id',r.document_id,
            'version_number',m.version_number,'baseline_run_id',NULL,'status','unavailable','revision',0,
            'compared_at',NULL,'entries','[]'::json,'limitations','["review_report_unavailable"]'::json),
          '{}'::json,'{}'::json
        FROM review_runs r JOIN document_family_versions m ON
          (m.organization_id,m.workspace_id,m.document_id)=(r.organization_id,r.workspace_id,r.document_id);
      CREATE TRIGGER document_family_versions_immutable BEFORE UPDATE OR DELETE ON document_family_versions
        FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();
      CREATE TRIGGER review_cycle_events_immutable BEFORE UPDATE OR DELETE ON review_cycle_events
        FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();
    """)


def downgrade() -> None:
    op.drop_table("review_cycle_events")
    op.drop_table("review_cycles")
    op.drop_table("document_family_versions")
    op.drop_table("document_families")
