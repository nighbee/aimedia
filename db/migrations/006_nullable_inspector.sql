-- Make inspector_id nullable for anonymous submissions
ALTER TABLE core.jobs ALTER COLUMN inspector_id DROP NOT NULL;
ALTER TABLE core.jobs DROP CONSTRAINT IF EXISTS jobs_inspector_id_fkey;
