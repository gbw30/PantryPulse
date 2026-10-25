-- Immutable facts and audit evidence. New revisions are INSERTs, never rewrites.
CREATE FUNCTION pp19_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'append-only record: insert a new revision or reversal'
    USING ERRCODE = '23514';
END;
$$;

DO $$
DECLARE relation_name text;
BEGIN
  FOREACH relation_name IN ARRAY ARRAY[
    'site_calendars', 'data_sources', 'demand_records', 'demand_revisions',
    'receipts', 'receipt_revisions', 'receipt_lines', 'donation_coverage_revisions',
    'stock_commands', 'receipt_postings', 'stock_ledger', 'audit_events', 'supply_receipts'
  ] LOOP
    EXECUTE format('CREATE TRIGGER immutable_fact BEFORE UPDATE OR DELETE ON %I '
                   'FOR EACH ROW EXECUTE FUNCTION pp19_immutable()', relation_name);
  END LOOP;
END;
$$;

CREATE FUNCTION pp19_calendar() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name = NEW.timezone) THEN
    RAISE EXCEPTION 'unknown site timezone' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER valid_calendar BEFORE INSERT ON site_calendars
  FOR EACH ROW EXECUTE FUNCTION pp19_calendar();

CREATE FUNCTION pp19_receipt_day() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE zone_name text;
BEGIN
  SELECT timezone INTO zone_name FROM site_calendars
    WHERE organization_id = NEW.organization_id AND id = NEW.calendar_version_id
      AND site_id = NEW.receiving_site_id;
  IF zone_name IS NULL OR (NEW.received_at AT TIME ZONE zone_name)::date <> NEW.local_day THEN
    RAISE EXCEPTION 'receipt local day/calendar mismatch' USING ERRCODE = '23514';
  END IF;
  -- Cannot spoof a previous transaction to append lines to an already committed event.
  NEW.ingest_transaction := txid_current();
  RETURN NEW;
END;
$$;
CREATE TRIGGER valid_receipt_day BEFORE INSERT ON receipt_revisions
  FOR EACH ROW EXECUTE FUNCTION pp19_receipt_day();

CREATE FUNCTION pp19_line_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_transaction bigint; parent_void boolean;
BEGIN
  SELECT ingest_transaction, is_void INTO parent_transaction, parent_void
    FROM receipt_revisions WHERE organization_id = NEW.organization_id
      AND id = NEW.receipt_revision_id;
  IF parent_transaction IS DISTINCT FROM txid_current() OR parent_void THEN
    RAISE EXCEPTION 'lines require a non-void revision created in the same transaction'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER complete_event_insert BEFORE INSERT ON receipt_lines
  FOR EACH ROW EXECUTE FUNCTION pp19_line_insert();

CREATE FUNCTION pp19_complete_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE has_lines boolean;
BEGIN
  SELECT EXISTS(SELECT 1 FROM receipt_lines WHERE organization_id = NEW.organization_id
    AND receipt_revision_id = NEW.id) INTO has_lines;
  IF has_lines = NEW.is_void THEN
    RAISE EXCEPTION 'received revision requires lines; void revision forbids lines'
      USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER complete_receipt AFTER INSERT ON receipt_revisions
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION pp19_complete_receipt();

CREATE FUNCTION pp19_product_unit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.base_unit IS DISTINCT FROM OLD.base_unit OR NEW.organization_id <> OLD.organization_id
     OR NEW.category_id <> OLD.category_id THEN
    RAISE EXCEPTION 'product ownership/category/base unit is immutable; create a new product'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER immutable_unit BEFORE UPDATE ON products
  FOR EACH ROW EXECUTE FUNCTION pp19_product_unit();

CREATE FUNCTION pp19_site_calendar_required() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM sites WHERE id = NEW.id AND active
             AND current_calendar_id IS NULL) THEN
    RAISE EXCEPTION 'active site requires an explicit current calendar'
      USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER site_calendar_required AFTER INSERT OR UPDATE ON sites
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION pp19_site_calendar_required();

CREATE FUNCTION pp19_supply_allocation() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE receipt_limit bigint; supply_limit bigint; original_delta bigint; net_amount numeric;
BEGIN
  -- Consistent lock order: supply then receipt line; aggregates run after locks.
  SELECT quantity INTO supply_limit FROM expected_supplies
    WHERE organization_id = NEW.organization_id AND id = NEW.supply_id FOR UPDATE;
  SELECT received_quantity INTO receipt_limit FROM receipt_lines
    WHERE organization_id = NEW.organization_id AND id = NEW.receipt_line_id FOR UPDATE;
  IF supply_limit IS NULL OR receipt_limit IS NULL THEN
    RAISE EXCEPTION 'allocation target missing' USING ERRCODE = '23514';
  END IF;
  SELECT COALESCE(sum(quantity_delta::numeric), 0) INTO net_amount FROM supply_receipts
    WHERE organization_id = NEW.organization_id AND receipt_line_id = NEW.receipt_line_id;
  IF net_amount < 0 OR net_amount > receipt_limit THEN
    RAISE EXCEPTION 'receipt quantity reused or over-reversed' USING ERRCODE = '23514';
  END IF;
  SELECT COALESCE(sum(quantity_delta::numeric), 0) INTO net_amount FROM supply_receipts
    WHERE organization_id = NEW.organization_id AND supply_id = NEW.supply_id;
  IF net_amount < 0 OR net_amount > supply_limit THEN
    RAISE EXCEPTION 'supply allocation exceeds quantity' USING ERRCODE = '23514';
  END IF;
  IF NEW.quantity_delta < 0 THEN
    SELECT quantity_delta INTO original_delta FROM supply_receipts
      WHERE organization_id = NEW.organization_id AND id = NEW.reverses_allocation_id;
    SELECT COALESCE(sum(quantity_delta::numeric), 0) INTO net_amount FROM supply_receipts
      WHERE organization_id = NEW.organization_id
        AND reverses_allocation_id = NEW.reverses_allocation_id;
    IF original_delta IS NULL OR original_delta <= 0 OR original_delta + net_amount < 0 THEN
      RAISE EXCEPTION 'invalid or excessive allocation reversal' USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NULL;
END;
$$;
CREATE TRIGGER bounded_supply_allocation AFTER INSERT ON supply_receipts
  FOR EACH ROW EXECUTE FUNCTION pp19_supply_allocation();
