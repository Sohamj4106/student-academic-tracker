-- Run this in pgAdmin Query Tool connected to student_academic_tracker.
-- This script adds a change log trigger to the tables already created.
-- It does not drop or replace existing tables.

CREATE OR REPLACE FUNCTION log_student_tracker_change()
RETURNS TRIGGER AS $$
DECLARE
    rid INTEGER;
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF TG_TABLE_NAME IN ('students', 'academic_records', 'semesters', 'gap_years', 'seminars', 'activities') THEN
            rid := OLD.student_id;
        ELSIF TG_TABLE_NAME = 'subjects' THEN
            rid := OLD.subject_id;
        ELSIF TG_TABLE_NAME = 'student_marks' THEN
            rid := OLD.mark_id;
        ELSE
            rid := NULL;
        END IF;
        INSERT INTO sync_log(operation, table_name, record_id, sync_status)
        VALUES ('DELETE', TG_TABLE_NAME, rid, 'Pending');
        RETURN OLD;
    ELSE
        IF TG_TABLE_NAME = 'students' THEN
            rid := NEW.student_id;
        ELSIF TG_TABLE_NAME = 'academic_records' THEN
            rid := NEW.student_id;
        ELSIF TG_TABLE_NAME = 'semesters' THEN
            rid := NEW.student_id;
        ELSIF TG_TABLE_NAME = 'gap_years' THEN
            rid := NEW.student_id;
        ELSIF TG_TABLE_NAME = 'seminars' THEN
            rid := NEW.student_id;
        ELSIF TG_TABLE_NAME = 'activities' THEN
            rid := NEW.student_id;
        ELSE
            rid := NULL;
        END IF;
        INSERT INTO sync_log(operation, table_name, record_id, sync_status)
        VALUES (TG_OP, TG_TABLE_NAME, rid, 'Pending');
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_students_sync ON students;
CREATE TRIGGER trg_students_sync AFTER INSERT OR UPDATE OR DELETE ON students
FOR EACH ROW EXECUTE FUNCTION log_student_tracker_change();

DROP TRIGGER IF EXISTS trg_academic_records_sync ON academic_records;
CREATE TRIGGER trg_academic_records_sync AFTER INSERT OR UPDATE OR DELETE ON academic_records
FOR EACH ROW EXECUTE FUNCTION log_student_tracker_change();

DROP TRIGGER IF EXISTS trg_semesters_sync ON semesters;
CREATE TRIGGER trg_semesters_sync AFTER INSERT OR UPDATE OR DELETE ON semesters
FOR EACH ROW EXECUTE FUNCTION log_student_tracker_change();

DROP TRIGGER IF EXISTS trg_subjects_sync ON subjects;
CREATE TRIGGER trg_subjects_sync AFTER INSERT OR UPDATE OR DELETE ON subjects
FOR EACH ROW EXECUTE FUNCTION log_student_tracker_change();

DROP TRIGGER IF EXISTS trg_student_marks_sync ON student_marks;
CREATE TRIGGER trg_student_marks_sync AFTER INSERT OR UPDATE OR DELETE ON student_marks
FOR EACH ROW EXECUTE FUNCTION log_student_tracker_change();

DROP TRIGGER IF EXISTS trg_gap_years_sync ON gap_years;
CREATE TRIGGER trg_gap_years_sync AFTER INSERT OR UPDATE OR DELETE ON gap_years
FOR EACH ROW EXECUTE FUNCTION log_student_tracker_change();

DROP TRIGGER IF EXISTS trg_seminars_sync ON seminars;
CREATE TRIGGER trg_seminars_sync AFTER INSERT OR UPDATE OR DELETE ON seminars
FOR EACH ROW EXECUTE FUNCTION log_student_tracker_change();

DROP TRIGGER IF EXISTS trg_activities_sync ON activities;
CREATE TRIGGER trg_activities_sync AFTER INSERT OR UPDATE OR DELETE ON activities
FOR EACH ROW EXECUTE FUNCTION log_student_tracker_change();

CREATE INDEX IF NOT EXISTS idx_sync_log_pending
ON sync_log(sync_status, sync_id);
